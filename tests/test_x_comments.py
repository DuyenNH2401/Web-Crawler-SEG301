import csv
import codecs
import json
import os
import tempfile
import unittest
from unittest.mock import patch

import database
import main
from x_crawler.export import COMMENT_COLUMNS, export_comments
from x_crawler.platforms.x import XCommentsCrawler, map_reply, parse_post_id
from x_crawler.platforms.x_browser import (
    SessionRejectedError, XBrowserCrawler, browser_post_url, load_cookies,
    map_visible_reply,
)


def reply(comment_id, parent_id, *, root="123", author="42", likes=2):
    return {
        "id": comment_id,
        "conversation_id": root,
        "text": f"Reply {comment_id}",
        "author_id": author,
        "created_at": "2026-10-04T12:30:00.000Z",
        "public_metrics": {"like_count": likes},
        "referenced_posts": [{"type": "replied_to", "id": parent_id}],
    }


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payloads):
        self.headers = {}
        self.payloads = list(payloads)
        self.calls = []

    def get(self, url, *, params, timeout):
        self.calls.append((url, params.copy(), timeout))
        return FakeResponse(self.payloads.pop(0))

    def close(self):
        pass


class XCommentTests(unittest.TestCase):
    def test_post_id_validation(self):
        self.assertEqual("123", parse_post_id("https://x.com/user/status/123?s=20"))
        self.assertEqual("123", parse_post_id("https://twitter.com/user/status/123"))
        self.assertEqual("123", parse_post_id("https://x.com/i/web/status/123"))
        with self.assertRaises(ValueError):
            parse_post_id("https://evil.example/user/status/123")

    def test_mapping_root_nested_and_invalid(self):
        users = {"42": {"name": "Example", "username": "example"}}
        direct = map_reply(reply("456", "123"), users, "123", "2026-10-05T00:00:00Z")
        nested = map_reply(reply("789", "456"), users, "123", "2026-10-05T00:00:00Z")
        self.assertEqual("ROOT", direct.parent_id)
        self.assertEqual("456", nested.parent_id)
        self.assertEqual("https://x.com/example/status/456", direct.comment_url)
        self.assertEqual("2026-10-04T12:30:00Z", direct.created_at)
        self.assertEqual(2, direct.like_count)
        bad = reply("999", "123", root="other")
        self.assertIsNone(map_reply(bad, users, "123", "2026-10-05T00:00:00Z"))
        no_time = reply("999", "123")
        del no_time["created_at"]
        self.assertIsNone(map_reply(no_time, users, "123", "2026-10-05T00:00:00Z"))

    def test_pagination_deduplication_and_export(self):
        session = FakeSession([
            {"data": [reply("456", "123")],
             "includes": {"users": [{"id": "42", "name": "Example", "username": "example"}]},
             "meta": {"next_token": "NEXT"}},
            {"data": [reply("456", "123"), reply("789", "456")],
             "meta": {"result_count": 2}},
        ])
        crawler = XCommentsCrawler("fake-token", session=session)
        comments = crawler.crawl("123")
        self.assertEqual(2, len(comments))
        self.assertEqual("conversation_id:123 is:reply -is:retweet", session.calls[0][1]["query"])
        self.assertEqual("NEXT", session.calls[1][1]["pagination_token"])
        self.assertEqual("Bearer fake-token", session.headers["Authorization"])

        with tempfile.TemporaryDirectory() as folder:
            db_path = os.path.join(folder, "comments.db")
            csv_path = os.path.join(folder, "comments.csv")
            database.upsert_comments(db_path, comments)
            database.upsert_comments(db_path, comments)
            rows = database.get_comments(db_path, "x", ["123"])
            self.assertEqual(2, len(rows))
            export_comments(rows, csv_path)
            with open(csv_path, newline="", encoding="utf-8-sig") as output:
                exported = list(csv.DictReader(output))
            with open(csv_path, "rb") as output:
                self.assertEqual(codecs.BOM_UTF8, output.read(3))
            self.assertEqual(list(COMMENT_COLUMNS), list(exported[0]))
            self.assertEqual("ROOT", exported[0]["parent_id"])
            self.assertEqual("456", exported[1]["parent_id"])
            self.assertTrue(all(value is not None for row in exported for value in row.values()))

    def test_csv_preserves_vietnamese_for_spreadsheet_apps(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "replies.csv")
            row = {column: "" for column in COMMENT_COLUMNS}
            row["content"] = "30ph mà bác tài vẫn đợi thì nể bác thật"
            export_comments([row], path)
            with open(path, encoding="utf-8-sig", newline="") as source:
                self.assertEqual(row["content"], next(csv.DictReader(source))["content"])

    def test_api_partial_errors_do_not_look_like_complete_results(self):
        session = FakeSession([{"data": [reply("456", "123")],
                                "errors": [{"detail": "Partial failure"}]}])
        with self.assertRaisesRegex(RuntimeError, "partial errors"):
            XCommentsCrawler("fake-token", session=session).crawl("123")

    def test_browser_mapping_keeps_unknown_fields_explicit(self):
        raw = {
            "url": "https://x.com/example/status/456",
            "created_at": "2026-10-04T12:30:00.000Z",
            "content": "  Hello from X  ",
            "author_name": "Example",
        }
        comment = map_visible_reply(raw, "123", "2026-10-05T00:00:00Z")
        self.assertEqual("456", comment.comment_id)
        self.assertEqual("Hello from X", comment.content)
        self.assertEqual("UNKNOWN", comment.parent_id)
        self.assertEqual("UNKNOWN", comment.author_id)
        self.assertEqual(0, comment.like_count)
        self.assertIsNone(map_visible_reply({**raw, "url": "https://x.com/example/status/123"},
                                            "123", "2026-10-05T00:00:00Z"))
        self.assertIsNone(map_visible_reply({**raw, "url": "https://example.com/status/789"},
                                            "123", "2026-10-05T00:00:00Z"))

    def test_browser_uses_supplied_permalink(self):
        self.assertEqual(
            "https://x.com/fromHD72/status/123",
            browser_post_url("https://x.com/fromHD72/status/123?ref=share"),
        )
        self.assertEqual("https://x.com/i/web/status/123", browser_post_url("123"))

    def test_cookie_file_is_loaded_for_x_without_exposing_values(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "cookies.json")
            with open(path, "w", encoding="utf-8") as output:
                json.dump({"auth_token": "sample-auth", "ct0": "sample-csrf"}, output)
            cookies = load_cookies(path)
            self.assertEqual(["auth_token", "ct0"], [cookie["name"] for cookie in cookies])
            self.assertTrue(all(cookie["domain"] == ".x.com" for cookie in cookies))
            self.assertTrue(cookies[0]["httpOnly"])
            self.assertFalse(cookies[1]["httpOnly"])
            with open(path, "w", encoding="utf-8") as output:
                json.dump({"auth_token": "sample-auth"}, output)
            with self.assertRaisesRegex(ValueError, "missing ct0"):
                load_cookies(path)

    def test_browser_mode_preserves_api_metadata_in_database(self):
        api_comment = map_reply(
            reply("456", "123"),
            {"42": {"name": "Example", "username": "example"}},
            "123", "2026-10-05T00:00:00Z",
        )
        browser_comment = map_visible_reply({
            "url": "https://x.com/example/status/456",
            "created_at": "2026-10-04T12:30:00.000Z",
            "content": "Updated text",
            "author_name": "Example",
        }, "123", "2026-10-05T01:00:00Z")
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "comments.db")
            database.upsert_comments(path, [api_comment])
            database.upsert_comments(path, [browser_comment])
            row = database.get_comments(path, "x", ["123"])[0]
            self.assertEqual("ROOT", row["parent_id"])
            self.assertEqual("42", row["author_id"])
            self.assertEqual(2, row["like_count"])
            self.assertEqual("Updated text", row["content"])

    def test_browser_crawl_reads_visible_cards_without_api(self):
        root = {"url": "https://x.com/example/status/123",
                "created_at": "2026-10-04T12:00:00Z", "content": "Root"}
        reply_card = {"url": "https://x.com/other/status/456",
                      "created_at": "2026-10-04T12:30:00Z", "content": "Reply"}

        class FakeLocator:
            def wait_for(self, **kwargs):
                pass

            @property
            def first(self):
                return self

            def evaluate_all(self, script):
                return [root, reply_card]

        class FakePage:
            def __init__(self):
                self.urls = []

            def goto(self, url, **kwargs):
                self.urls.append(url)

            def locator(self, selector):
                return FakeLocator()

            def evaluate(self, script):
                pass

            def wait_for_timeout(self, milliseconds):
                pass

        crawler = XBrowserCrawler.__new__(XBrowserCrawler)
        crawler.page = FakePage()
        crawler._ready = True
        crawler._session_expected = False
        crawler.headless = False
        comments = crawler.crawl("123", max_scrolls=5)
        self.assertEqual(["456"], [comment.comment_id for comment in comments])
        self.assertEqual(["https://x.com/i/web/status/123"], crawler.page.urls)

        crawler.page.urls.clear()
        crawler.crawl("https://x.com/fromHD72/status/123", max_scrolls=5)
        self.assertEqual(["https://x.com/fromHD72/status/123"], crawler.page.urls)

    def test_browser_navigation_error_has_actionable_message(self):
        crawler = XBrowserCrawler.__new__(XBrowserCrawler)
        crawler._session_expected = False

        class FailingPage:
            def goto(self, url, **kwargs):
                raise RuntimeError("net::ERR_HTTP_RESPONSE_CODE_FAILURE")

        crawler.page = FailingPage()
        with self.assertRaisesRegex(RuntimeError, "retry without --headless"):
            crawler._open_post("https://x.com/fromHD72/status/123")

    def test_browser_reports_discarded_cookies(self):
        crawler = XBrowserCrawler.__new__(XBrowserCrawler)
        crawler._session_expected = True

        class PublicPage:
            def goto(self, url, **kwargs):
                return None

        class EmptySession:
            def cookies(self, url):
                return []

        crawler.page = PublicPage()
        crawler.context = EmptySession()
        with self.assertRaisesRegex(SessionRejectedError, "did not retain"):
            crawler._open_post("https://x.com/fromHD72/status/123")

    def test_visible_browser_can_recover_with_manual_login(self):
        class Session:
            logged_in = False

            def cookies(self, url):
                if self.logged_in:
                    return [{"name": "auth_token"}, {"name": "ct0"}]
                return []

        class Locator:
            @property
            def first(self):
                return self

            def wait_for(self, **kwargs):
                pass

            def evaluate_all(self, script):
                return [
                    {"url": "https://x.com/fromHD72/status/123",
                     "created_at": "2026-10-04T12:00:00Z", "content": "Root"},
                    {"url": "https://x.com/other/status/456",
                     "created_at": "2026-10-04T12:30:00Z", "content": "Reply"},
                ]

        class Page:
            def goto(self, url, **kwargs):
                return None

            def locator(self, selector):
                return Locator()

            def evaluate(self, script):
                pass

            def wait_for_timeout(self, milliseconds):
                pass

        crawler = XBrowserCrawler.__new__(XBrowserCrawler)
        crawler.context = Session()
        crawler.page = Page()
        crawler._ready = True
        crawler._session_expected = True
        crawler.headless = False

        def finish_login(prompt):
            crawler.context.logged_in = True
            return ""

        with patch("builtins.input", side_effect=finish_login):
            comments = crawler.crawl("https://x.com/fromHD72/status/123", max_scrolls=1)
        self.assertEqual(["456"], [comment.comment_id for comment in comments])
        self.assertTrue(crawler._ready)

    def test_cli_defaults_to_browser_without_bearer_token(self):
        browser_options = {}

        class FakeBrowserCrawler:
            def __init__(self, profile_dir, **kwargs):
                self.profile_dir = profile_dir
                browser_options.update(kwargs)

            def crawl(self, post_id, **kwargs):
                return [map_visible_reply({
                    "url": "https://x.com/example/status/456",
                    "created_at": "2026-10-04T12:30:00Z",
                    "content": "Reply",
                }, post_id, "2026-10-05T00:00:00Z")]

            def close(self):
                pass

        with tempfile.TemporaryDirectory() as folder:
            db_path = os.path.join(folder, "comments.db")
            out_path = os.path.join(folder, "comments.csv")
            with patch.dict(os.environ, {"X_BEARER_TOKEN": ""}), patch(
                "x_crawler.platforms.x_browser.XBrowserCrawler", FakeBrowserCrawler
            ):
                result = main.main(["--post", "123", "--db", db_path,
                                    "--output", out_path])
            self.assertEqual(0, result)
            self.assertEqual("chrome", browser_options["browser_channel"])
            self.assertIsNone(browser_options["cookie_file"])
            with open(out_path, newline="", encoding="utf-8-sig") as output:
                exported = list(csv.DictReader(output))
            self.assertEqual("456", exported[0]["comment_id"])


if __name__ == "__main__":
    unittest.main()
