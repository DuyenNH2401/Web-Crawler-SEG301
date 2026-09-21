import unittest
from pathlib import Path

import parser as bbc_parser
from config import (
    ALLOWED_DOMAINS,
    IGNORED_EXTENSIONS,
    IGNORED_PATHS,
    IGNORED_SCHEMES,
)


ROOT = Path(__file__).resolve().parents[1]
TOPIC_FIXTURE = next((ROOT / "examples" / "a_topic").glob("BBC Business*.html"))
ARTICLE_FIXTURE = next(
    (ROOT / "examples" / "an_article").glob("Russia's elections*.html")
)


class BBCParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.topic_html = TOPIC_FIXTURE.read_text(encoding="utf-8", errors="replace")
        cls.article_html = ARTICLE_FIXTURE.read_text(
            encoding="utf-8", errors="replace"
        )

    def test_bbc_article_url_formats(self):
        accepted = (
            "https://www.bbc.com/news/articles/c8vgyzn2d31yo",
            "https://www.bbc.co.uk/sport/football/articles/c1234567890o",
            "https://www.bbc.com/news/world-europe-5122661",
            "https://www.bbc.com/news/world-europe-5122661.html",
        )
        rejected = (
            "https://www.bbc.com/business",
            "https://www.bbc.com/news/videos/cjp30pq0rx6ro",
            "https://www.bbc.com/news/live/c1234567890o",
            "https://www.bbc.com/search?q=economy",
            "https://evilbbc.com/news/articles/c8vgyzn2d31yo",
        )

        for url in accepted:
            with self.subTest(url=url):
                self.assertTrue(bbc_parser.is_article_url(url))
        for url in rejected:
            with self.subTest(url=url):
                self.assertFalse(bbc_parser.is_article_url(url))

    def test_topic_extracts_meaningful_non_media_cards(self):
        data = bbc_parser.parse_page_data(
            self.topic_html, "https://www.bbc.com/business", 0, 200
        )
        self.assertEqual(
            data["title"],
            "BBC Business | Economy, Tech, AI, Work, Personal Finance, Market news",
        )
        self.assertIn(
            "US and China discuss AI safety plan ahead of Trump-Xi summit",
            data["content"],
        )
        self.assertNotIn("Sign up to World of Business", data["content"])
        self.assertNotIn("Why planning can be a form of procrastination", data["content"])
        self.assertNotIn("Advertisement", data["content"])

    def test_article_extracts_body_without_media_ads_or_metadata(self):
        data = bbc_parser.parse_page_data(
            self.article_html,
            "https://www.bbc.com/news/articles/cx4gqv239043o",
            1,
            200,
        )

        self.assertEqual(
            data["title"],
            "Russia's elections had few surprises - but how the Kremlin uses the results will be crucial",
        )
        self.assertTrue(data["content"].startswith("Many things about Russia"))
        for excluded_text in (
            "Advertisement",
            "Steve Rosenberg BBC Russia editor",
            "'No surprises' as results emerge",
            "Emil Leegunov/Anadolu via Getty Images",
        ):
            with self.subTest(excluded_text=excluded_text):
                self.assertNotIn(excluded_text, data["content"])

    def test_topic_links_include_articles_and_exclude_video(self):
        links = bbc_parser.extract_and_filter_links(
            self.topic_html,
            "https://www.bbc.com/business",
            ALLOWED_DOMAINS,
            IGNORED_EXTENSIONS,
            IGNORED_SCHEMES,
            IGNORED_PATHS,
            articles_only=True,
        )

        self.assertIn(
            "https://www.bbc.com/news/articles/c8vgyzn2d31yo", links
        )
        self.assertTrue(links)
        self.assertTrue(all(bbc_parser.is_article_url(url) for url in links))
        self.assertFalse(any("/videos/" in url for url in links))

    def test_article_query_and_fragment_are_removed(self):
        html = """
        <a href="/news/articles/c8vgyzn2d31yo?at_medium=test#section">Story</a>
        <a href="/news/videos/cjp30pq0rx6ro">Video</a>
        """
        links = bbc_parser.extract_and_filter_links(
            html,
            "https://www.bbc.com/business",
            ALLOWED_DOMAINS,
            IGNORED_EXTENSIONS,
            IGNORED_SCHEMES,
            IGNORED_PATHS,
            articles_only=True,
        )
        self.assertEqual(
            links, ["https://www.bbc.com/news/articles/c8vgyzn2d31yo"]
        )

    def test_content_mode_keeps_topics_and_live_text_but_filters_media(self):
        html = """
        <nav><a href="/news">Global navigation is not crawl content</a></nav>
        <main>
          <a href="/business/world-of-business">Business topic</a>
          <a href="/news/live/c1234567890o">Live text page</a>
          <a href="/news/articles/c8vgyzn2d31yo">Article</a>
          <a href="/news/videos/cjp30pq0rx6ro">Video</a>
          <a href="/reel/video/p0lvwbpd/watch">Reel video</a>
          <a href="/audio/play/w3ct8ggc">Audio</a>
        </main>
        """
        links = bbc_parser.extract_and_filter_links(
            html,
            "https://www.bbc.com/business",
            ALLOWED_DOMAINS,
            IGNORED_EXTENSIONS,
            IGNORED_SCHEMES,
            IGNORED_PATHS,
            articles_only=False,
        )
        self.assertEqual(
            links,
            [
                "https://www.bbc.com/business/world-of-business",
                "https://www.bbc.com/news/live/c1234567890o",
                "https://www.bbc.com/news/articles/c8vgyzn2d31yo",
            ],
        )

    def test_legacy_promo_layout_keeps_text_and_drops_video_and_image_alt(self):
        html = """
        <html><head><title>Business - BBC News</title></head><body><main>
          <div data-testid="promo">
            <a href="/business/world-of-business">
              <p class="x-PromoHeadline">Useful topic headline</p>
            </a>
            <p class="x-Paragraph">Useful description text.</p>
            <img alt="Meaningless image caption">
          </div>
          <div data-testid="promo">
            <a href="/news/videos/cjp30pq0rx6ro">
              <p class="x-PromoHeadline">Video headline</p>
            </a>
          </div>
        </main></body></html>
        """
        data = bbc_parser.parse_page_data(
            html, "https://www.bbc.co.uk/news/business", 0, 200
        )
        self.assertEqual(
            data["content"], "Useful topic headline\nUseful description text."
        )
        self.assertNotIn("Video headline", data["content"])
        self.assertNotIn("Meaningless image caption", data["content"])


if __name__ == "__main__":
    unittest.main()
