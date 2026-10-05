"""Offline checks for the shared CLI and Reddit storage adapter."""

import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import main
from shared_database import import_threads_dataset
from tiktok_crawler.comments_db import save_comments


class UnifiedCliTests(unittest.TestCase):
    def test_reddit_import_and_dry_run_share_requested_database(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / "comments.db"
            source = root / "reddit.jsonl"
            source.write_text(json.dumps({"id": "abc123", "post_id": "t3_post123",
                                          "parent_id": "t3_post123", "subreddit": "python",
                                          "body": "hello", "score": -2,
                                          "created_utc": 1728000000}) + "\n", encoding="utf-8")
            args = ["--db", str(target), "reddit", "import", "--subreddit", "python",
                    "--max-comments", "1", "--input", str(source)]
            self.assertEqual(main.main([*args, "--dry-run"]), 0)
            self.assertFalse(target.exists())
            self.assertEqual(main.main(args), 0)
            with closing(sqlite3.connect(target)) as conn:
                rows = conn.execute("SELECT platform, comment_id, like_count FROM comments").fetchall()
            self.assertEqual(rows, [("reddit", "abc123", 0)])

    def test_youtube_receives_shared_database_path(self):
        with tempfile.TemporaryDirectory() as folder, patch("main.subprocess.call", return_value=0) as call:
            target = Path(folder) / "all.db"
            self.assertEqual(main.main(["--db", str(target), "youtube", "--url", "video"]), 0)
            command = call.call_args.args[0]
            self.assertEqual(command[-2:], ["--db", str(target.resolve())])
            self.assertNotIn("cwd", call.call_args.kwargs)

    def test_tiktok_writes_shared_schema_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "all.db"
            row = {"cid": "comment1", "post_id": "video1", "text": "Tiếng Việt",
                   "username": "alice", "likes": 3, "created_at": "2026-10-05 12:00:00"}
            self.assertEqual(save_comments([row], target), 1)
            self.assertEqual(save_comments([row], target), 1)
            with closing(sqlite3.connect(target)) as conn:
                result = conn.execute("SELECT platform, content, COUNT(*) FROM comments").fetchone()
            self.assertEqual(result, ("tiktok", "Tiếng Việt", 1))

    def test_tiktok_command_uses_shared_database(self):
        with tempfile.TemporaryDirectory() as folder, patch(
            "tiktok_crawler.main.run", new_callable=AsyncMock
        ) as crawl:
            target = Path(folder) / "all.db"
            self.assertEqual(main.main(["--db", str(target), "tiktok", "https://www.tiktok.com/@a/video/123"]), 0)
            self.assertEqual(crawl.call_args.args[-1], str(target.resolve()))

    def test_threads_import_preserves_multiple_post_contexts(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, target = root / "dataset.sqlite3", root / "all.db"
            with closing(sqlite3.connect(source)) as conn, conn:
                conn.execute("CREATE TABLE comments(platform, comment_id, post_id, payload)")
                payload = json.dumps({"content": "hello", "author_name": "alice",
                                      "comment_url": "https://threads.com/c", "created_at": None})
                conn.executemany("INSERT INTO comments VALUES ('threads', 'c1', ?, ?)",
                                 [("post1", payload), ("post2", payload)])
            self.assertEqual(import_threads_dataset(target, source), 1)
            self.assertEqual(import_threads_dataset(target, source), 0)
            with closing(sqlite3.connect(target)) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM threads_comment_context").fetchone()[0], 2)


if __name__ == "__main__":
    unittest.main()
