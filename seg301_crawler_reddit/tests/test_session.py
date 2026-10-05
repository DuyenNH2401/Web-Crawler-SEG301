import io
import json
from contextlib import closing, redirect_stderr, redirect_stdout
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

from reddit_app.clients import load_session_cookies
from reddit_app.main import main


class Response(io.BytesIO):
    status = 200
    headers = {}
    def __init__(self, value):
        super().__init__(json.dumps(value).encode())


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "cookies.txt"

    def test_cookie_header_loads_without_losing_encoded_values(self):
        self.path.write_text("Cookie: reddit_session=secret%2Fabc; preferences=encoded%3Dvalue\n")
        jar = load_session_cookies(self.path)
        request = urllib.request.Request("https://www.reddit.com/r/python/new.json")
        jar.add_cookie_header(request)
        self.assertEqual(request.get_header("Cookie"), "reddit_session=secret%2Fabc; preferences=encoded%3Dvalue")

    def test_session_cookies_are_not_sent_to_other_domains_or_insecure_http(self):
        self.path.write_text("reddit_session=secret")
        jar = load_session_cookies(self.path)
        for url in ("https://example.org/", "https://reddit.com.evil.example/",
                    "https://other.www.reddit.com/", "http://www.reddit.com/"):
            with self.subTest(url=url):
                request = urllib.request.Request(url)
                jar.add_cookie_header(request)
                self.assertIsNone(request.get_header("Cookie"))

    def test_invalid_cookie_file_errors_do_not_echo_credentials(self):
        for content in ("", "secret-invalid-cookie", "reddit_session=secret\nX-Injected: secret", "secret[bad]=value"):
            with self.subTest(content=content):
                self.path.write_text(content)
                with self.assertRaises(ValueError) as caught:
                    load_session_cookies(self.path)
                self.assertNotIn("secret", str(caught.exception))

    def test_escaped_control_characters_are_rejected_without_echoing_cookie(self):
        self.path.write_text(r'reddit_session="\015\012X-Injected: secret"')
        with self.assertRaises(ValueError) as caught:
            load_session_cookies(self.path)
        self.assertNotIn("secret", str(caught.exception))

    def test_missing_cookie_file_does_not_create_database(self):
        db = Path(self.tmp.name) / "new.sqlite3"
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(["crawl-session", "--cookies-file", str(self.path), "--subreddit", "python",
                                   "--max-comments", "1", "--db", str(db)]), 1)
        self.assertFalse(db.exists())

    def test_session_cli_stores_comments_and_does_not_log_cookie(self):
        self.path.write_text("reddit_session=secret")
        db = Path(self.tmp.name) / "session.sqlite3"
        requested = []
        def transport(opener, request, *, timeout):
            # Exercise the actual domain-scoped cookie middleware before the mocked transport.
            for handler in opener.handlers:
                if isinstance(handler, urllib.request.HTTPCookieProcessor):
                    handler.https_request(request)
            requested.append(request)
            if "/new.json" in request.full_url:
                return Response(dict(kind="Listing", data=dict(children=[dict(kind="t3", data=dict(id="p1"))], after=None)))
            return Response([{}, dict(kind="Listing", data=dict(children=[dict(kind="t1", data=dict(
                id="c1", body="synthetic", link_id="t3_p1", parent_id="t3_p1", subreddit="python"))]))])
        with patch("urllib.request.OpenerDirector.open", transport), \
             redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()) as logs:
            self.assertEqual(main(["crawl-session", "--cookies-file", str(self.path), "--subreddit", "python",
                                   "--max-comments", "1", "--max-posts", "1", "--request-delay", "0.001",
                                   "--db", str(db)]), 0)
        self.assertEqual(json.loads(output.getvalue())["created"], 1)
        self.assertEqual(len(requested), 2)
        self.assertTrue(all(request.get_header("Cookie") == "reddit_session=secret" for request in requested))
        self.assertNotIn("secret", output.getvalue() + logs.getvalue())
        with closing(sqlite3.connect(db)) as conn:
            self.assertEqual(conn.execute("SELECT platform, comment_id, content FROM comments").fetchone(),
                             ("reddit", "c1", "synthetic"))

    def test_session_403_stops_without_logging_cookie(self):
        self.path.write_text("reddit_session=secret")
        requested = []
        def transport(opener, request, *, timeout):
            requested.append(request)
            raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, io.BytesIO())
        with patch("urllib.request.OpenerDirector.open", transport), redirect_stderr(io.StringIO()) as logs:
            self.assertEqual(main(["crawl-session", "--cookies-file", str(self.path), "--subreddit", "python",
                                   "--max-comments", "1", "--db", str(Path(self.tmp.name) / "session.sqlite3")]), 1)
        self.assertEqual(len(requested), 1)
        self.assertIn("403", logs.getvalue())
        self.assertNotIn("secret", logs.getvalue())


if __name__ == "__main__":
    unittest.main()
