import io
import json
from contextlib import closing, redirect_stdout
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import urllib.error
import sqlite3
import socket
import ssl
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from reddit_app.clients import PublicReddit
from reddit_app.database import Store
from reddit_app.crawler import crawl
from reddit_app.main import main


class Response(io.BytesIO):
    status = 200
    headers = {}

    def __init__(self, data):
        super().__init__(json.dumps(data).encode())


def listing(children, after=None):
    return dict(kind="Listing", data=dict(children=children, after=after))


def post(pid):
    return dict(kind="t3", data=dict(id=pid))


def comment(cid, *, replies="", body="synthetic"):
    return dict(kind="t1", data=dict(id=cid, body=body, author="user123", author_fullname="t2_user123",
                                    parent_id="t3_p1", link_id="t3_p1", subreddit="python",
                                    score=2, created_utc=100, permalink=f"/r/python/comments/p1/thread/{cid}/",
                                    replies=replies))


class PublicTests(unittest.TestCase):
    def test_request_start_is_visible_before_transport_returns(self):
        def opener(request, *, timeout):
            self.assertEqual(timeout, 10)
            self.assertTrue(any("request start" in line for line in logs.output))
            self.assertTrue(any("path=/r/python/new.json" in line for line in logs.output))
            self.assertNotIn("secret", "\n".join(logs.output))
            raise TimeoutError("secret transport details")
        reddit = PublicReddit(opener=opener, timeout=10, user_agent="secret user agent")
        with self.assertLogs("reddit_crawler", level="INFO") as logs:
            with self.assertRaisesRegex(ValueError, "timeout"):
                list(reddit.subreddit("python").new(limit=1))

    def test_public_cli_runs_without_credentials_and_writes_requested_schema(self):
        def opener(request, *, timeout):
            if "/new.json" in request.full_url:
                return Response(listing([post("p1")]))
            return Response([listing([]), listing([comment("c1")])])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "public.sqlite3"
            with patch.dict("os.environ", {}, clear=True), patch("urllib.request.urlopen", opener), \
                 patch("time.sleep"), redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(["crawl-public", "--subreddit", "python", "--max-comments", "1",
                                       "--max-posts", "1", "--request-delay", "0.001", "--db", str(path)]), 0)
            self.assertEqual(json.loads(output.getvalue())["created"], 1)
            with closing(sqlite3.connect(path)) as conn:
                self.assertEqual(conn.execute("SELECT platform, comment_id, content FROM comments").fetchone(),
                                 ("reddit", "c1", "synthetic"))

    def test_public_pagination_obeys_post_limit_without_credentials(self):
        requested = []
        def opener(request, *, timeout):
            requested.append(request)
            self.assertEqual(timeout, 30)
            if len(requested) == 1:
                return Response(listing([post("p1")], after="t3_p1"))
            return Response(listing([post("p2"), post("p3")]))
        reddit = PublicReddit(opener=opener, sleep=lambda seconds: None)
        posts = list(reddit.subreddit("python").new(limit=2))
        self.assertEqual([p.id for p in posts], ["p1", "p2"])
        self.assertEqual(len(requested), 2)
        query = parse_qs(urlparse(requested[1].full_url).query)
        self.assertEqual(query["after"], ["t3_p1"])
        self.assertEqual(query["limit"], ["1"])
        for request in requested:
            self.assertIsNone(request.get_header("Authorization"))
            self.assertIsNone(request.get_header("Cookie"))

    def test_public_comments_include_replies_and_report_unexpanded_branches(self):
        def opener(request, *, timeout):
            if "/new.json" in request.full_url:
                return Response(listing([post("p1")]))
            reply = comment("c2")
            reply["data"]["parent_id"] = "t1_c1"
            root = comment("c1", replies=listing([reply]))
            return Response([listing([]), listing([root, dict(kind="more", data={})])])
        reddit = PublicReddit(opener=opener, sleep=lambda seconds: None)
        with Store(":memory:") as store:
            result = crawl(reddit, store, "python", max_comments=2, more_limit=0)
            self.assertEqual(result["saved"], 2)
            self.assertEqual(result["unexpanded_branches"], 1)
            rows = store.conn.execute("SELECT * FROM comments ORDER BY comment_id").fetchall()
            self.assertEqual(rows[0]["author_id"], "user123")
            self.assertEqual(rows[1]["parent_id"], "t1_c1")
            self.assertEqual(rows[0]["comment_url"], "https://www.reddit.com/r/python/comments/p1/thread/c1/")

    def test_forbidden_stops_without_retry_or_switching_endpoints(self):
        requests = []
        def opener(request, *, timeout):
            requests.append(request)
            raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, io.BytesIO())
        reddit = PublicReddit(opener=opener, sleep=lambda seconds: None)
        with self.assertRaisesRegex(ValueError, "403"):
            list(reddit.subreddit("python").new(limit=1))
        self.assertEqual(len(requests), 1)

    def test_rate_limit_respects_retry_after_and_stays_on_same_endpoint(self):
        requested = []
        waits = []
        def opener(request, *, timeout):
            requested.append(request.full_url)
            if len(requested) == 1:
                raise urllib.error.HTTPError(request.full_url, 429, "limited", {"Retry-After": "7"}, io.BytesIO())
            return Response(listing([post("p1")]))
        reddit = PublicReddit(opener=opener, sleep=waits.append)
        self.assertEqual(len(list(reddit.subreddit("python").new(limit=1))), 1)
        self.assertIn(7, waits)
        self.assertEqual(requested[0], requested[1])

    def test_network_failure_is_explained_without_writing_fake_data(self):
        def opener(request, *, timeout):
            raise urllib.error.URLError(socket.gaierror(socket.EAI_AGAIN, "DNS unavailable"))
        reddit = PublicReddit(opener=opener, sleep=lambda seconds: None)
        with Store(":memory:") as store:
            with self.assertRaisesRegex(ValueError, "DNS.*gaierror"):
                crawl(reddit, store, "python", max_comments=10, more_limit=0)
            self.assertEqual(store.ids(), [])

    def test_connect_failure_reports_underlying_category_without_secret_text(self):
        cases = [
            (urllib.error.URLError(TimeoutError("secret timeout text")), "timeout"),
            (urllib.error.URLError(ssl.SSLCertVerificationError(1, "secret certificate text")), "chứng chỉ TLS"),
            (urllib.error.URLError(ConnectionRefusedError(111, "secret proxy text")), "TCP bị từ chối"),
            (urllib.error.URLError("https://user:secret@example.test"), "lỗi kết nối mạng"),
        ]
        for error, expected in cases:
            with self.subTest(expected=expected):
                def opener(request, *, timeout):
                    raise error
                reddit = PublicReddit(opener=opener)
                with self.assertRaisesRegex(ValueError, expected) as caught:
                    list(reddit.subreddit("python").new(limit=1))
                self.assertNotIn("secret", str(caught.exception))

    def test_timeout_while_reading_response_uses_network_diagnostic(self):
        class SlowResponse(Response):
            def read(self, size=-1):
                raise TimeoutError("private response context")
        response = SlowResponse({})
        reddit = PublicReddit(opener=lambda request, timeout: response)
        with self.assertRaisesRegex(ValueError, "timeout") as caught:
            list(reddit.subreddit("python").new(limit=1))
        self.assertNotIn("private", str(caught.exception))
        self.assertTrue(response.closed)

    def test_invalid_listing_does_not_silently_report_success(self):
        reddit = PublicReddit(opener=lambda request, timeout: Response({}), sleep=lambda seconds: None)
        with self.assertRaisesRegex(ValueError, "JSON"):
            list(reddit.subreddit("python").new(limit=1))


if __name__ == "__main__":
    unittest.main()
