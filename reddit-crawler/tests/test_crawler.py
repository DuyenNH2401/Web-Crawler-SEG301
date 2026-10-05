import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from reddit_app import RedditClient, Store, crawl, database_stats, main, show_comments


def sample_comment(cid="c1", body="hello", parent="t3_p1"):
    return {
        "id": cid,
        "body": body,
        "parent_id": parent,
        "link_id": "t3_p1",
        "score": 4,
        "created_utc": 100.0,
        "subreddit": "python",
        "permalink": f"/r/python/comments/p1/thread/{cid}/",
    }


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.sqlite3"
        self.store = Store(self.db_path)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.store.close)

    def rows(self):
        return self.store.conn.execute("SELECT * FROM comments").fetchall()

    def test_save_and_update_comment(self):
        self.assertEqual(self.store.save(sample_comment(), now=100), "created")
        self.assertEqual(self.store.save(sample_comment(body="edited"), now=200), "updated")
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["content"], "edited")
        self.assertEqual(rows[0]["collected_at"], 100)

    def test_reply_preserves_parent_and_post(self):
        self.store.save(sample_comment("c2", parent="t1_c1"), now=100)
        row = self.rows()[0]
        self.assertEqual(row["parent_id"], "t1_c1")
        self.assertEqual(row["post_id"], "t3_p1")

    def test_deleted_body_erases_previous_content(self):
        for body in ("[deleted]", "[removed]"):
            self.store.save(sample_comment(), now=100)
            self.assertEqual(self.store.save(sample_comment(body=body), now=200), "deleted")
            self.assertEqual(self.rows(), [])

    def test_database_has_requested_11_columns(self):
        self.store.save(sample_comment(), now=100)
        expected = [
            "platform", "comment_id", "content", "author_id", "author_name",
            "parent_id", "post_id", "comment_url", "created_at", "like_count", "collected_at"
        ]
        self.assertEqual(list(self.rows()[0].keys()), expected)

    def test_author_and_url_normalization(self):
        source = sample_comment()
        source["author"] = "user123"
        source["author_fullname"] = "t2_author123"
        self.store.save(source, now=200)
        row = dict(self.rows()[0])
        self.assertEqual(row["author_id"], "author123")
        self.assertEqual(row["author_name"], "user123")
        self.assertEqual(row["comment_url"], "https://www.reddit.com/r/python/comments/p1/thread/c1/")

    def test_negative_score_preserved(self):
        source = sample_comment()
        source["score"] = -5
        self.store.save(source, now=100)
        self.assertEqual(self.rows()[0]["like_count"], -5)


class CrawlerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "test.sqlite3")
        self.addCleanup(self.store.close)

    def test_crawl_limits_and_duplicates(self):
        class MockReddit:
            def new_posts(self, subreddit, limit=100):
                return ["p1", "p2"]

            def comments(self, subreddit, post_id):
                if post_id == "p1":
                    return [sample_comment("c1"), sample_comment("c2", parent="t1_c1")], 1
                return [sample_comment("c2"), sample_comment("c3")], 0

        res = crawl(MockReddit(), self.store, "python", max_comments=2)
        self.assertEqual(res["saved"], 2)
        self.assertEqual(res["posts"], 1)
        self.assertEqual(res["created"], 2)
        self.assertTrue(res["limit_reached"])
        self.assertEqual(len(self.store.ids()), 2)

    def test_crawl_dry_run_leaves_db_empty(self):
        class MockReddit:
            def new_posts(self, subreddit, limit=100):
                return ["p1"]

            def comments(self, subreddit, post_id):
                return [sample_comment("c1")], 0

        res = crawl(MockReddit(), self.store, "python", max_comments=10, dry_run=True)
        self.assertEqual(res["would_save"], 1)
        self.assertEqual(res["saved"], 1)
        self.assertEqual(len(self.store.ids()), 0)


class ClientTests(unittest.TestCase):
    def test_load_cookie_strips_header_prefix(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "cookie.txt"
            f.write_text("Cookie: session=xyz123\n")
            client = RedditClient(f)
            self.assertEqual(client.cookie, "session=xyz123")

    def test_comments_parses_nested_replies(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "cookie.txt"
            f.write_text("session=test")
            client = RedditClient(f)

            raw_response = [
                {},
                {
                    "data": {
                        "children": [
                            {
                                "kind": "t1",
                                "data": {
                                    "id": "c1",
                                    "body": "top level",
                                    "replies": {
                                        "data": {
                                            "children": [
                                                {"kind": "t1", "data": {"id": "c2", "body": "reply"}},
                                                {"kind": "more", "data": {}}
                                            ]
                                        }
                                    }
                                }
                            }
                        ]
                    }
                }
            ]

            with patch.object(client, "_get", return_value=raw_response):
                comments, unexpanded = client.comments("python", "p1")
                self.assertEqual(len(comments), 2)
                self.assertEqual([c["id"] for c in comments], ["c1", "c2"])
                self.assertEqual(unexpanded, 1)


class ParserTests(unittest.TestCase):
    def test_parse_posts_extracts_t3_ids(self):
        from reddit_app.parser import parse_posts
        data = {"data": {"children": [{"kind": "t3", "data": {"id": "p1"}}, {"kind": "t1", "data": {"id": "c1"}}]}}
        self.assertEqual(parse_posts(data), ["p1"])

    def test_normalize_comment_strips_t2_and_adds_prefix_t3(self):
        from reddit_app.parser import normalize_comment
        raw = {"id": "c1", "author": "dev", "author_fullname": "t2_devid", "link_id": "p1", "permalink": "/r/python/c1"}
        norm = normalize_comment(raw)
        self.assertEqual(norm["author_id"], "devid")
        self.assertEqual(norm["post_id"], "t3_p1")
        self.assertEqual(norm["comment_url"], "https://www.reddit.com/r/python/c1")


class CliTests(unittest.TestCase):
    def test_stats_and_show_cli(self):
        with tempfile.TemporaryDirectory() as d:
            db_path = Path(d) / "test.sqlite3"
            with Store(db_path) as store:
                store.save(sample_comment("c1", body="hello world"))

            stats = database_stats(db_path)
            self.assertEqual(stats["comments"], 1)
            self.assertEqual(stats["subreddits"][0]["subreddit"], "python")

            output = io.StringIO()
            with patch("sys.stdout", output):
                show_comments(db_path, limit=5)
            self.assertIn("hello world", output.getvalue())


if __name__ == "__main__":
    unittest.main()
