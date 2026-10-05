import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from reddit_app.database import Store
from reddit_app.crawler import crawl, import_jsonl, sync
from reddit_app.network import request_with_backoff
from reddit_app.main import main


def comment(cid="c1", body="hello", parent="t3_p1"):
    return SimpleNamespace(id=cid, body=body, parent_id=parent,
                           link_id="t3_p1", score=4, created_utc=100.0,
                           edited=False, subreddit=SimpleNamespace(display_name="python"),
                           permalink=f"/r/python/comments/p1/thread/{cid}/")


def json_record(cid="c1", subreddit="python", body="synthetic"):
    return dict(id=cid, subreddit=subreddit, body=body, post_id="p1",
                parent_id="t3_p1", score=1, created_utc=100)


class Forest:
    def __init__(self, comments, remaining=()):
        self.comments = comments
        self.remaining = remaining
        self.limit = None

    def replace_more(self, *, limit):
        self.limit = limit
        return self.remaining

    def list(self):
        return self.comments


class Reddit:
    def __init__(self, posts=(), returned=()):
        self.posts = posts
        self.returned = returned
        self.requested_limit = None
        self.requested_ids = []

    def subreddit(self, name):
        self.name = name
        return self

    def new(self, *, limit):
        self.requested_limit = limit
        return iter(self.posts[:limit])

    def info(self, *, fullnames):
        self.requested_ids.extend(fullnames)
        return iter(c for c in self.returned if f"t1_{c.id}" in fullnames)


class StoreFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "comments.sqlite3")
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.store.close)

    def rows(self):
        return self.store.conn.execute("SELECT * FROM comments").fetchall()


class StoreTests(StoreFixture):
    def test_repeated_crawl_updates_existing_record(self):
        self.assertEqual(self.store.save(comment(), now=100), "created")
        self.assertEqual(self.store.save(comment(body="edited"), now=200), "updated")
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["content"], "edited")
        self.assertEqual(rows[0]["collected_at"], 100)

    def test_reply_preserves_parent_and_post(self):
        self.store.save(comment("c2", parent="t1_c1"), now=100)
        row = self.rows()[0]
        self.assertEqual(row["parent_id"], "t1_c1")
        self.assertEqual(row["post_id"], "t3_p1")

    def test_deleted_or_removed_body_erases_previous_content(self):
        for body in ("[deleted]", "[removed]"):
            self.store.save(comment(), now=100)
            self.assertEqual(self.store.save(comment(body=body), now=200), "deleted")
            self.assertEqual(self.rows(), [])

    def test_retention_uses_first_collection_not_refresh_time(self):
        self.store.save(comment(), now=100)
        self.store.save(comment(body="changed"), now=999)
        self.store.save(comment("c2"), now=1000)
        self.assertEqual(self.store.purge(now=1000, retention_hours=0.25), 1)
        self.assertEqual(self.store.ids(), ["c2"])

    def test_sql_like_comment_body_is_stored_literally(self):
        body = "'); DROP TABLE comments; --"
        self.store.save(comment(body=body), now=100)
        self.assertEqual(self.rows()[0]["content"], body)

    def test_database_has_requested_columns(self):
        self.store.save(comment(), now=100)
        self.assertEqual(list(self.rows()[0].keys()), [
            "platform", "comment_id", "content", "author_id", "author_name", "parent_id",
            "post_id", "comment_url", "created_at", "like_count", "collected_at"])

    def test_api_mapping_includes_author_url_and_reddit_score(self):
        source = comment()
        source.author = SimpleNamespace(name="user123")
        source.author_fullname = "t2_author123"
        self.store.save(source, now=200)
        row = dict(self.rows()[0])
        self.assertEqual(row, dict(platform="reddit", comment_id="c1", content="hello",
                                  author_id="author123", author_name="user123", parent_id="t3_p1",
                                  post_id="t3_p1", comment_url="https://www.reddit.com/r/python/comments/p1/thread/c1/",
                                  created_at=100, like_count=4, collected_at=200))

    def test_missing_fields_are_sql_null(self):
        self.store.save({"comment_id": "abcxyz"}, now=200)
        row = dict(self.rows()[0])
        self.assertEqual(row.pop("platform"), "reddit")
        self.assertEqual(row.pop("comment_id"), "abcxyz")
        self.assertEqual(row.pop("collected_at"), 200)
        self.assertTrue(all(value is None for value in row.values()))

    def test_deleted_account_clears_previous_author_fields(self):
        source = comment()
        source.author = SimpleNamespace(name="user123")
        source.author_fullname = "t2_author123"
        self.store.save(source, now=100)
        source.author = None
        self.store.save(source, now=200)
        row = self.rows()[0]
        self.assertIsNone(row["author_id"])
        self.assertIsNone(row["author_name"])
        self.assertEqual(row["content"], "hello")

    def test_author_id_is_null_when_not_supplied_without_fetching_profile(self):
        class Author:
            name = "user123"
            @property
            def id(self):
                raise AssertionError("must not fetch a user profile")
        source = comment()
        source.author = Author()
        self.store.save(source, now=200)
        self.assertEqual(self.rows()[0]["author_name"], "user123")
        self.assertIsNone(self.rows()[0]["author_id"])

    def test_negative_reddit_score_is_preserved(self):
        source = comment()
        source.score = -3
        self.store.save(source, now=100)
        self.assertEqual(self.rows()[0]["like_count"], -3)

    def test_invalid_retention_is_rejected(self):
        with self.assertRaises(ValueError):
            self.store.purge(now=100, retention_hours=0)


class CrawlTests(StoreFixture):
    def test_limits_posts_and_comments_and_preserves_replies(self):
        forest = Forest([comment(), comment("c2", parent="t1_c1"), comment("c3")], [object()])
        post = SimpleNamespace(id="p1", comments=forest)
        reddit = Reddit([post, SimpleNamespace(id="p2")])
        result = crawl(reddit, self.store, "python", max_posts=1, max_comments=2, more_limit=3)
        self.assertEqual(reddit.requested_limit, 1)
        self.assertEqual(forest.limit, 3)
        self.assertEqual(result["posts"], 1)
        self.assertEqual(result["created"], 2)
        self.assertEqual(result["unexpanded_branches"], 1)
        self.assertTrue(result["limit_reached"])
        self.assertEqual(len(self.rows()), 2)

    def test_dry_run_does_not_modify_content(self):
        self.store.save(comment(), now=100)
        post = SimpleNamespace(id="p1", comments=Forest([comment(body="[deleted]"), comment("c2")]))
        result = crawl(Reddit([post]), self.store, "python", max_comments=10, dry_run=True)
        self.assertEqual(result["processed"], 2)
        self.assertEqual(result["would_delete"], 1)
        self.assertEqual(result["would_save"], 1)
        self.assertEqual(self.rows()[0]["content"], "hello")

    def test_total_limit_spans_posts_and_skips_deleted_and_duplicate_ids(self):
        posts = [SimpleNamespace(id="p1", comments=Forest([comment(body="[deleted]"), comment("c2")])),
                 SimpleNamespace(id="p2", comments=Forest([comment("c2"), comment("c3"), comment("c4")]))]
        result = crawl(Reddit(posts), self.store, "python", max_comments=2)
        self.assertEqual(result["saved"], 2)
        self.assertEqual(self.store.ids(), ["c2", "c3"])

    def test_does_not_request_another_post_after_reaching_total_limit(self):
        def posts(*, limit):
            yield SimpleNamespace(id="p1", comments=Forest([comment()]))
            self.fail("requested another post after reaching the limit")
        reddit = Reddit()
        reddit.new = posts
        crawl(reddit, self.store, "python", max_comments=1)
        self.assertEqual(self.store.ids(), ["c1"])

    def test_failed_sync_batch_keeps_previous_content(self):
        self.store.save(comment(), now=100)
        def info(*, fullnames):
            raise ConnectionError("offline")
            yield
        reddit = Reddit()
        reddit.info = info
        with self.assertRaises(ConnectionError):
            sync(reddit, self.store)
        self.assertEqual(self.rows()[0]["content"], "hello")

    def test_sync_refreshes_and_removes_deleted_and_missing_comments(self):
        for cid in ("c1", "c2", "c3"):
            self.store.save(comment(cid), now=100)
        result = sync(Reddit(returned=[comment(body="changed"), comment("c2", "[deleted]")]), self.store)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["deleted"], 2)
        self.assertEqual(self.store.ids(), ["c1"])
        self.assertEqual(self.rows()[0]["content"], "changed")

    def test_sync_batches_requests(self):
        for i in range(205):
            self.store.save(comment(f"c{i}"), now=100)
        reddit = Reddit()
        batch_sizes = []
        def info(*, fullnames):
            batch_sizes.append(len(fullnames))
            return iter(())
        reddit.info = info
        sync(reddit, self.store)
        self.assertEqual(batch_sizes, [100, 100, 5])
        self.assertEqual(self.store.ids(), [])


class ImportTests(StoreFixture):
    def write_jsonl(self, rows):
        path = Path(self.tmp.name) / "input.jsonl"
        path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
        return path

    def record(self, cid="c1", subreddit="python", body="synthetic"):
        return json_record(cid, subreddit, body)

    def test_import_filters_subreddit_and_limits_unique_valid_comments(self):
        path = self.write_jsonl([self.record(subreddit="other"), self.record(),
                                self.record(), self.record("c2"), self.record("c3")])
        result = import_jsonl(path, self.store, "python", max_comments=2)
        self.assertEqual(result["saved"], 2)
        self.assertEqual(self.store.ids(), ["c1", "c2"])

    def test_import_deletion_erases_stored_comment(self):
        self.store.save(comment(), now=100)
        path = self.write_jsonl([self.record(body="[deleted]")])
        result = import_jsonl(path, self.store, "python", max_comments=2)
        self.assertEqual(result["deleted"], 1)
        self.assertEqual(self.rows(), [])

    def test_invalid_input_does_not_echo_content(self):
        path = self.write_jsonl([dict(body="private text")])
        with self.assertRaisesRegex(ValueError, "line 1") as error:
            import_jsonl(path, self.store, "python", max_comments=2)
        self.assertNotIn("private text", str(error.exception))

    def test_import_requested_format_with_missing_fields_and_no_subreddit(self):
        path = self.write_jsonl([dict(platform="reddit", comment_id="abcxyz", content="I agree with this",
                                     author_id="user123", author_name="user123", parent_id="t3_xxx",
                                     post_id="t3_xxx", created_at=100, like_count=12)])
        result = import_jsonl(path, self.store, "python", max_comments=1)
        self.assertEqual(result["saved"], 1)
        row = self.rows()[0]
        self.assertEqual(row["comment_id"], "abcxyz")
        self.assertEqual(row["post_id"], "t3_xxx")
        self.assertEqual(row["author_id"], "user123")
        self.assertIsNone(row["comment_url"])


class RetryTests(unittest.TestCase):
    def response(self, status, headers=None):
        return SimpleNamespace(status_code=status, headers=headers or {}, close=lambda: None)

    def test_rate_limit_respects_retry_after(self):
        responses = iter([self.response(429, {"Retry-After": "7"}), self.response(200)])
        waits = []
        result = request_with_backoff(lambda: next(responses), sleep=waits.append)
        self.assertEqual(waits, [7])
        self.assertEqual(result.status_code, 200)

    def test_transient_server_errors_have_bounded_retries(self):
        statuses = []
        waits = []
        def send():
            statuses.append(503)
            return self.response(503)
        result = request_with_backoff(send, sleep=waits.append)
        self.assertEqual(len(statuses), 3)
        self.assertEqual(waits, [1, 2])
        self.assertEqual(result.status_code, 503)

    def test_forbidden_is_not_retried(self):
        waits = []
        result = request_with_backoff(lambda: self.response(403), sleep=waits.append)
        self.assertEqual(result.status_code, 403)
        self.assertEqual(waits, [])


def legacy_database(path):
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("""CREATE TABLE comments (
            id TEXT PRIMARY KEY, post_id TEXT NOT NULL, parent_id TEXT NOT NULL,
            subreddit TEXT NOT NULL, body TEXT NOT NULL, score INTEGER NOT NULL,
            created_utc REAL NOT NULL, edited_utc REAL, collected_at REAL NOT NULL,
            updated_at REAL NOT NULL)""")
        conn.execute("CREATE INDEX comments_subreddit ON comments(subreddit)")
        conn.execute("CREATE INDEX comments_collected ON comments(collected_at)")
        conn.execute("INSERT INTO comments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     ("c1", "p1", "t3_p1", "python", "legacy content", 4, 100, None, 200, 300))
        conn.commit()


class MigrationTests(unittest.TestCase):
    def test_legacy_schema_migrates_without_losing_content_or_retention(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "old.sqlite3"
            legacy_database(path)
            with Store(path) as store:
                row = dict(store.conn.execute("SELECT * FROM comments").fetchone())
                self.assertEqual(row["comment_id"], "c1")
                self.assertEqual(row["post_id"], "t3_p1")
                self.assertEqual(row["content"], "legacy content")
                self.assertEqual(row["created_at"], 100)
                self.assertEqual(row["collected_at"], 200)
                for field in ("author_id", "author_name", "comment_url"):
                    self.assertIsNone(row[field])
                self.assertEqual(store.conn.execute("SELECT subreddit FROM comment_metadata").fetchone()[0], "python")
                store.save(comment(body="updated"), now=300)
                self.assertEqual(store.conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0], 1)
                store.delete("c1")
                self.assertEqual(store.conn.execute("SELECT COUNT(*) FROM comment_metadata").fetchone()[0], 0)
            with Store(path) as store:
                self.assertEqual(store.ids(), [])

    def test_unknown_schema_is_left_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "other.sqlite3"
            with closing(sqlite3.connect(path)) as conn:
                conn.execute("CREATE TABLE comments (custom TEXT)")
                conn.execute("INSERT INTO comments VALUES ('keep this')")
                conn.commit()
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "schema"):
                Store(path)
            self.assertEqual(path.read_bytes(), before)


class CliTests(unittest.TestCase):
    def test_legacy_dry_run_and_stats_preserve_original_database_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "old.sqlite3"
            source = Path(directory) / "source.jsonl"
            legacy_database(path)
            source.write_text(json.dumps(json_record()), encoding="utf-8")
            before = path.read_bytes()
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(["stats", "--db", str(path)]), 0)
            self.assertEqual(json.loads(output.getvalue())["comments"], 1)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["import", "--input", str(source), "--subreddit", "python",
                                       "--max-comments", "1", "--db", str(path), "--dry-run"]), 0)
            self.assertEqual(path.read_bytes(), before)

    def test_import_dry_run_does_not_create_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "new.sqlite3"
            source = Path(directory) / "source.jsonl"
            source.write_text(json.dumps(json_record()), encoding="utf-8")
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(["import", "--input", str(source), "--subreddit", "python",
                                       "--max-comments", "10", "--db", str(path), "--dry-run"]), 0)
            self.assertEqual(json.loads(output.getvalue())["would_save"], 1)
            self.assertFalse(path.exists())

    def test_missing_credentials_fails_before_creating_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "new.sqlite3"
            with patch.dict("os.environ", {}, clear=True), redirect_stderr(io.StringIO()):
                self.assertEqual(main(["crawl", "--subreddit", "python", "--max-comments", "10",
                                       "--db", str(path)]), 1)
            self.assertFalse(path.exists())

    def test_stats_of_absent_database_does_not_create_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "new.sqlite3"
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(["stats", "--db", str(path)]), 0)
            self.assertEqual(json.loads(output.getvalue())["comments"], 0)
            self.assertFalse(path.exists())

    def test_purge_removes_expired_rows_without_api_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "comments.sqlite3"
            with Store(path) as store:
                store.save(comment(), now=0)
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(["purge", "--db", str(path)]), 0)
            self.assertEqual(json.loads(output.getvalue())["purged"], 1)
            with closing(sqlite3.connect(path)) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
