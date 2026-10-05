"""
Test offline (khong goi mang). Chay:
    python -m unittest discover -s tests -v
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from crawler import YouTubeCommentCrawler  # noqa: E402
from database import Database  # noqa: E402
from normalizer import count_words, parse_like_count, parse_relative_time, to_record  # noqa: E402
from youtube_parser import (  # noqa: E402
    extract_initial_data,
    extract_innertube_config,
    extract_video_id,
    find_comment_section_token,
    parse_next_response,
)

VIDEO = "SGZkBoBsxsk"
REF = datetime(2026, 10, 5, 12, 0, 0, tzinfo=config.TIMEZONE)


# ---------- Fixture: du lieu gia lap giong YouTube ----------
def cont(token):
    return {"continuationItemRenderer": {"continuationEndpoint": {"continuationCommand": {"token": token}}}}


def entity(key, cid, text, author="UCaaa", name="@nguyenvana", published="2 days ago", likes="1.2K"):
    return {"entityKey": key, "payload": {"commentEntityPayload": {
        "key": key,
        "properties": {"commentId": cid, "content": {"content": text}, "publishedTime": published},
        "author": {"channelId": author, "displayName": name},
        "toolbar": {"likeCountNotliked": likes, "likeCountA11y": f"{likes} likes"},
    }}}


INITIAL_DATA = {"contents": {"twoColumnWatchNextResults": {"results": {"results": {"contents": [
    {"videoPrimaryInfoRenderer": {"title": {"runs": [{"text": "MỜI LƠI CÓ NÊN HAY KHÔNG?"}]}}},
    {"itemSectionRenderer": {"sectionIdentifier": "comment-item-section", "contents": [cont("T0")]}},
]}}}}}

HTML = (
    "<html><script>var ytInitialData = " + json.dumps(INITIAL_DATA, ensure_ascii=False)
    + ";</script><script>ytcfg.set({\"INNERTUBE_API_KEY\":\"KEY1\","
    "\"INNERTUBE_CLIENT_VERSION\":\"2.20261001.00.00\"});</script></html>"
)

RESPONSES = {
    # trang dau: header + menu sap xep (Top, Newest)
    "T0": {"onResponseReceivedEndpoints": [{"reloadContinuationItemsCommand": {"continuationItems": [
        {"commentsHeaderRenderer": {
            "countText": {"runs": [{"text": "222"}, {"text": " Comments"}]},
            "sortMenu": {"sortFilterSubMenuRenderer": {"subMenuItems": [
                {"serviceEndpoint": {"continuationCommand": {"token": "TOP"}}},
                {"serviceEndpoint": {"continuationCommand": {"token": "NEW"}}},
            ]}}}},
    ]}}]},
    # dinh dang MOI: commentViewModel + entity mutations, comment 1 co reply
    "NEW": {
        "onResponseReceivedEndpoints": [{"reloadContinuationItemsCommand": {"continuationItems": [
            {"commentThreadRenderer": {
                "commentViewModel": {"commentViewModel": {"commentKey": "k1"}},
                "replies": {"commentRepliesRenderer": {"contents": [cont("R1")]}},
            }},
            {"commentThreadRenderer": {"commentViewModel": {"commentViewModel": {"commentKey": "k2"}}}},
            cont("P2"),
        ]}}],
        "frameworkUpdates": {"entityBatchUpdate": {"mutations": [
            entity("k1", "Ugx1", "người miền nam nói chuyện dễ thương ghê"),
            entity("k2", "Ugx2", "😂😂", author="", name="", likes=""),
        ]}},
    },
    # reply trang 1 -> con trang reply 2
    "R1": {
        "onResponseReceivedEndpoints": [{"appendContinuationItemsAction": {"continuationItems": [
            {"commentViewModel": {"commentViewModel": {"commentKey": "k3"}}},
            {"continuationItemRenderer": {"button": {"buttonRenderer": {"command": {
                "continuationCommand": {"token": "R2"}}}}}},
        ]}}],
        "frameworkUpdates": {"entityBatchUpdate": {"mutations": [
            entity("k3", "Ugx1.r1", "đồng ý với bạn luôn đó nha", published="5 hours ago", likes="3"),
        ]}},
    },
    "R2": {
        "onResponseReceivedEndpoints": [{"appendContinuationItemsAction": {"continuationItems": [
            {"commentViewModel": {"commentViewModel": {"commentKey": "k4"}}},
        ]}}],
        "frameworkUpdates": {"entityBatchUpdate": {"mutations": [
            entity("k4", "Ugx1.r2", "reply thứ hai nè mọi người", published="1 week ago (edited)"),
        ]}},
    },
    # dinh dang CU: commentRenderer; Ugx1 trung -> phai bo
    "P2": {"onResponseReceivedEndpoints": [{"appendContinuationItemsAction": {"continuationItems": [
        {"commentThreadRenderer": {"comment": {"commentRenderer": {
            "commentId": "Ugx4",
            "contentText": {"runs": [{"text": "video này hay quá "}, {"text": "mọi người ơi"}]},
            "authorText": {"simpleText": "@tranb"},
            "authorEndpoint": {"browseEndpoint": {"browseId": "UCbbb"}},
            "publishedTimeText": {"runs": [{"text": "1 month ago"}]},
            "voteCount": {"simpleText": "15"},
        }}}},
        {"commentThreadRenderer": {"comment": {"commentRenderer": {
            "commentId": "Ugx1", "contentText": {"simpleText": "người miền nam nói chuyện dễ thương ghê"},
        }}}},
    ]}}]},
}
RESPONSES["TOP"] = RESPONSES["NEW"]  # che do "Hang dau" dung cung du lieu


class FakeClient:
    def __init__(self):
        self.calls = []

    def fetch_watch_page(self, video_id):
        assert video_id == VIDEO
        return extract_initial_data(HTML)

    def next(self, token):
        self.calls.append(token)
        return RESPONSES[token]


# ---------- Tests ----------
class TestVideoId(unittest.TestCase):
    def test_variants(self):
        for url in [
            "https://www.youtube.com/watch?v=SGZkBoBsxsk",
            "https://m.youtube.com/watch?v=SGZkBoBsxsk&t=30s",
            "https://youtu.be/SGZkBoBsxsk?si=abc",
            "https://www.youtube.com/shorts/SGZkBoBsxsk",
            "youtube.com/live/SGZkBoBsxsk",
            "SGZkBoBsxsk",
        ]:
            self.assertEqual(extract_video_id(url), VIDEO, url)

    def test_invalid(self):
        self.assertIsNone(extract_video_id("https://www.youtube.com/@khoice"))
        self.assertIsNone(extract_video_id("https://fakeyoutube.com/watch?v=SGZkBoBsxsk"))


class TestHtml(unittest.TestCase):
    def test_initial_data_and_config(self):
        data = extract_initial_data(HTML)
        self.assertEqual(find_comment_section_token(data), "T0")
        self.assertEqual(extract_innertube_config(HTML), ("KEY1", "2.20261001.00.00"))

    def test_json_containing_script_tag(self):
        tricky = {"x": "};</script>", "contents": INITIAL_DATA["contents"]}
        html = "var ytInitialData = " + json.dumps(tricky) + ";</script>"
        self.assertEqual(extract_initial_data(html)["x"], "};</script>")


class TestNormalizer(unittest.TestCase):
    def test_relative_time(self):
        self.assertEqual(parse_relative_time("2 days ago", REF), datetime(2026, 10, 3, 12, tzinfo=config.TIMEZONE))
        self.assertEqual(parse_relative_time("5 hours ago (edited)", REF).hour, 7)
        self.assertEqual(parse_relative_time("3 ngày trước", REF).day, 2)
        self.assertEqual(parse_relative_time("just now", REF), REF)
        self.assertIsNone(parse_relative_time("", REF))
        self.assertIsNone(parse_relative_time("hôm qua", REF))

    def test_like_count(self):
        cases = {"": 0, "15": 15, "1.2K": 1200, "1,2K": 1200, "3M": 3_000_000,
                 "1,234": 1234, "12 likes": 12, "1.5K likes": 1500, None: 0}
        for text, expected in cases.items():
            self.assertEqual(parse_like_count(text), expected, text)

    def test_word_count(self):
        self.assertEqual(count_words("người miền nam, nói!"), 4)
        self.assertEqual(count_words("😂😂"), 0)

    def test_defaults_not_null(self):
        rec = to_record({"comment_id": "c1", "content": "hi"}, VIDEO, None, REF)
        self.assertEqual(rec["author_id"], "UNKNOWN")
        self.assertEqual(rec["author_name"], "UNKNOWN")
        self.assertEqual(rec["parent_id"], "ROOT")
        self.assertEqual(rec["like_count"], 0)
        self.assertEqual(rec["created_at"], "2026-10-05 12:00:00")  # khong parse duoc -> collected_at
        self.assertTrue(all(v is not None for v in rec.values()))
        self.assertIsNone(to_record({"comment_id": "c1", "content": "  "}, VIDEO, None, REF))


class TestParseResponse(unittest.TestCase):
    def test_new_format(self):
        page = parse_next_response(RESPONSES["NEW"])
        self.assertEqual([c["comment_id"] for c in page["comments"]], ["Ugx1", "Ugx2"])
        self.assertEqual(page["comments"][0]["reply_token"], "R1")
        self.assertEqual(page["comments"][0]["author_id"], "UCaaa")
        self.assertEqual(page["next_token"], "P2")

    def test_header(self):
        page = parse_next_response(RESPONSES["T0"])
        self.assertEqual(page["sort_tokens"], ["TOP", "NEW"])
        self.assertEqual(page["total_text"], "222 Comments")


class TestCrawlerEndToEnd(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.client = FakeClient()
        self.crawler = YouTubeCommentCrawler(self.db, client=self.client)

    def tearDown(self):
        self.db.close()

    def rows(self):
        return [dict(r) for r in self.db.conn.execute("SELECT * FROM comments ORDER BY id")]

    def test_full_crawl(self):
        n = self.crawler.crawl_video(f"https://youtu.be/{VIDEO}", max_comments=0, sort="newest")
        self.assertEqual(n, 5)
        # T0 -> NEW (doi sang Moi nhat) -> reply R1, R2 -> trang P2
        self.assertEqual(self.client.calls, ["T0", "NEW", "R1", "R2", "P2"])
        rows = {r["comment_id"]: r for r in self.rows()}
        self.assertEqual(set(rows), {"Ugx1", "Ugx2", "Ugx1.r1", "Ugx1.r2", "Ugx4"})

        root = rows["Ugx1"]
        self.assertEqual(root["platform"], "youtube")
        self.assertEqual(root["parent_id"], "ROOT")
        self.assertEqual(root["post_id"], VIDEO)
        self.assertEqual(root["author_id"], "UCaaa")
        self.assertEqual(root["author_name"], "@nguyenvana")
        self.assertEqual(root["like_count"], 1200)
        self.assertEqual(root["comment_url"], f"https://www.youtube.com/watch?v={VIDEO}&lc=Ugx1")

        self.assertEqual(rows["Ugx1.r1"]["parent_id"], "Ugx1")
        self.assertEqual(rows["Ugx1.r2"]["parent_id"], "Ugx1")
        self.assertEqual(rows["Ugx2"]["author_id"], "UNKNOWN")   # quy uoc NOT NULL
        self.assertEqual(rows["Ugx4"]["author_id"], "UCbbb")     # dinh dang cu
        self.assertEqual(rows["Ugx4"]["content"], "video này hay quá mọi người ơi")
        self.assertEqual(self.crawler.stats["duplicates"], 1)    # Ugx1 lap lai o P2

    def test_limit_and_options(self):
        self.assertEqual(self.crawler.crawl_video(VIDEO, max_comments=2), 2)
        self.assertEqual(len(self.rows()), 2)

    def test_no_replies_min_words_top(self):
        n = self.crawler.crawl_video(VIDEO, include_replies=False, min_words=4, sort="top")
        self.assertEqual(self.client.calls, ["T0", "TOP", "P2"])  # khong goi R1/R2
        self.assertEqual(n, 2)  # Ugx1 + Ugx4; "😂😂" (0 tu) bi loc
        self.assertEqual(self.crawler.stats["skipped_short"], 1)

    def test_recrawl_updates_not_duplicates(self):
        self.crawler.crawl_video(VIDEO)
        RESPONSES_LIKES = self.rows()[0]["like_count"]
        self.crawler.crawl_video(VIDEO)
        self.assertEqual(len(self.rows()), 5)
        self.assertEqual(self.rows()[0]["like_count"], RESPONSES_LIKES)

    def test_export(self):
        self.crawler.crawl_video(VIDEO)
        with tempfile.TemporaryDirectory() as d:
            csv_path = os.path.join(d, "out.csv")
            self.assertEqual(self.db.export_csv(csv_path), 5)
            with open(csv_path, encoding="utf-8-sig") as f:
                header = f.readline().strip().split(",")
            self.assertEqual(header, config.EXPORT_COLUMNS)
            jsonl = os.path.join(d, "out.jsonl")
            self.assertEqual(self.db.export_jsonl(jsonl, post_id=VIDEO), 5)
            with open(jsonl, encoding="utf-8") as f:
                first = json.loads(f.readline())
            self.assertNotIn("id", first)
            self.assertEqual(list(first), config.EXPORT_COLUMNS)


if __name__ == "__main__":
    unittest.main()
