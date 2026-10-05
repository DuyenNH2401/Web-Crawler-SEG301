import io
import json
from contextlib import redirect_stderr, redirect_stdout
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from reddit_app.progress import CrawlProgress
from reddit_app.clients import PublicReddit
from reddit_app.database import Store
from reddit_app.crawler import crawl
from reddit_app.main import main


class ProgressTests(unittest.TestCase):
    def test_cli_enables_progress_without_polluting_json_stdout(self):
        def opener(request, *, timeout):
            data = dict(kind="Listing", data=dict(children=[
                dict(kind="t3", data=dict(id="p1"))], after=None))
            if "/new.json" not in request.full_url:
                data = [{}, dict(kind="Listing", data=dict(children=[
                    dict(kind="t1", data=dict(id="c1", body="synthetic"))]))]
            response = io.BytesIO(json.dumps(data).encode())
            response.status = 200
            response.headers = {}
            return response
        with patch("urllib.request.urlopen", opener), redirect_stdout(io.StringIO()) as output, \
             redirect_stderr(io.StringIO()) as logs:
            status = main(["crawl-public", "--subreddit", "python", "--max-comments", "50",
                           "--max-posts", "1", "--request-delay", "0.001", "--dry-run"])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.getvalue())["would_save"], 1)
        self.assertIn("Đang cào (dry-run) 1/50", logs.getvalue())
        self.assertIn("Hoàn tất", logs.getvalue())
        self.assertFalse(any(worker.name == "reddit-progress" for worker in threading.enumerate()))

    def test_status_continues_while_transport_is_waiting(self):
        heartbeat = threading.Event()
        lines = []
        def emit(line):
            lines.append(line)
            if "Đang lấy JSON" in line:
                heartbeat.set()
        def opener(request, *, timeout):
            self.assertTrue(heartbeat.wait(1), "no status while waiting on HTTP")
            raise TimeoutError("secret transport details")
        progress = CrawlProgress(50, interval=0.005, emit=emit)
        with self.assertRaisesRegex(ValueError, "timeout"):
            with progress:
                reddit = PublicReddit(opener=opener, progress=progress)
                list(reddit.subreddit("python").new(limit=1))
        self.assertFalse(progress.worker.is_alive())
        self.assertTrue(any("0/50" in line for line in lines))
        self.assertIn("Lỗi", lines[-1])
        self.assertNotIn("secret", "\n".join(lines))

    def test_counts_follow_unique_saved_comments_and_report_partial_completion(self):
        comments = [dict(id="c1", body="synthetic"), dict(id="c1", body="duplicate"),
                    dict(id="c2", body="[deleted]"), dict(id="c3", body="synthetic")]
        forest = SimpleNamespace(replace_more=lambda **kwargs: [], list=lambda: comments)
        reddit = SimpleNamespace(subreddit=lambda name: SimpleNamespace(
            new=lambda **kwargs: iter([SimpleNamespace(id="p1", comments=forest)])))
        lines = []
        with CrawlProgress(50, emit=lines.append) as progress, Store(":memory:") as store:
            result = crawl(reddit, store, "python", max_comments=50, progress=progress)
        self.assertEqual(result["saved"], 2)
        self.assertTrue(any("1/50" in line for line in lines))
        self.assertIn("2/50", lines[-1])
        self.assertIn("bài=1", lines[-1])
        self.assertIn("Hoàn tất", lines[-1])
        self.assertFalse(progress.worker.is_alive())

    def test_dry_run_is_labeled_and_elapsed_time_is_shown(self):
        lines = []
        with CrawlProgress(50, dry_run=True, emit=lines.append) as progress:
            progress.update(saved=1, posts=1, stage="Kiểm tra comment", report=True)
        self.assertTrue(all("dry-run" in line for line in lines))
        self.assertIn("1/50", lines[-1])
        self.assertRegex(lines[-1], r"elapsed=\d{2}:\d{2}:\d{2}")

    def test_keyboard_interrupt_stops_worker_and_reports_interruption(self):
        lines = []
        progress = CrawlProgress(50, emit=lines.append)
        with self.assertRaises(KeyboardInterrupt):
            with progress:
                raise KeyboardInterrupt
        self.assertFalse(progress.worker.is_alive())
        self.assertIn("Đã dừng", lines[-1])
        self.assertIn("0/50", lines[-1])


if __name__ == "__main__":
    unittest.main()
