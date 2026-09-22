import unittest
from unittest.mock import patch

from crawler import CrawlerEngine
from sources.base import SourceAdapter
from sources.bbc import BBCSource


class _Response:
    status_code = 200
    headers = {"Content-Type": "text/html; charset=utf-8"}

    def __init__(self, url: str):
        self.url = url
        self.text = url


class _Session:
    def __init__(self):
        self.headers = {}

    def get(self, url: str, timeout: int):
        return _Response(url)

    def close(self):
        pass


class _Source(SourceAdapter):
    name = "Test source"
    seed_urls = ["https://example.com/"]
    allowed_domains = ["example.com"]
    headers = {"User-Agent": "test"}
    max_depth = 1
    max_pages = 10
    request_timeout = 1
    crawl_delay = 0

    def is_allowed_url(self, url: str) -> bool:
        return url.startswith("https://example.com/")

    def is_article_candidate(self, url: str, depth: int, html_content: str) -> bool:
        return depth == 1

    def parse_page_data(self, html_content: str, url: str, depth: int, status_code: int):
        return {
            "url": url,
            "domain": "example.com",
            "title": url.rsplit("/", 1)[-1] or "seed",
            "content": "content",
            "depth": depth,
            "status_code": status_code,
            "crawled_at": "2026-01-01T00:00:00",
        }

    def extract_links(self, html_content: str, current_url: str):
        if current_url == self.seed_urls[0]:
            return [
                "https://example.com/article-1",
                "https://example.com/article-2",
            ]
        return []


class CrawlerLimitTests(unittest.TestCase):
    def _crawl(self, max_articles=None):
        engine = CrawlerEngine(db_path="unused-test.db")
        with (
            patch("crawler.requests.Session", _Session),
            patch("crawler.RobotsManager.is_allowed", return_value=True),
            patch("crawler.database.init_db"),
            patch("crawler.database.insert_page"),
            patch("crawler.database.insert_links"),
            patch("crawler.time.sleep"),
        ):
            articles = engine.crawl(
                _Source(),
                max_articles=max_articles,
                max_pages=10,
                max_depth=1,
                crawl_delay=0,
            )
        return articles, engine.stats

    def test_default_article_limit_does_not_stop_after_first_article(self):
        articles, stats = self._crawl()

        self.assertEqual(2, len(articles))
        self.assertEqual(3, stats["pages_crawled"])

    def test_explicit_article_limit_still_stops_early(self):
        articles, stats = self._crawl(max_articles=1)

        self.assertEqual(1, len(articles))
        self.assertEqual(2, stats["pages_crawled"])


class BBCConfigurationTests(unittest.TestCase):
    def test_seed_uses_working_bbc_news_host(self):
        source = BBCSource()

        self.assertEqual(["https://www.bbc.co.uk/news"], source.seed_urls)
        self.assertTrue(source.is_allowed_url(source.seed_urls[0]))


if __name__ == "__main__":
    unittest.main()
