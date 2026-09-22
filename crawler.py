"""Shared BFS crawler engine for all configured news-source adapters."""

import time
from typing import Dict, List
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

import database
from config import DB_PATH
from models import Article
from sources.base import SourceAdapter
from url_frontier import URLFrontier


class RobotsManager:
    """Cache robots.txt decisions per host, matching the original crawler."""

    def __init__(self, headers: Dict[str, str], timeout: int):
        self.headers = headers
        self.user_agent = headers.get("User-Agent", "*")
        self.timeout = timeout
        self.parsers: Dict[str, RobotFileParser] = {}

    def is_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain not in self.parsers:
            rp = RobotFileParser()
            robots_url = f"{parsed.scheme}://{domain}/robots.txt"
            try:
                response = requests.get(
                    robots_url,
                    headers=self.headers,
                    timeout=self.timeout,
                )
                if response.status_code == 200:
                    rp.parse(response.text.splitlines())
                else:
                    rp.allow_all = True
            except Exception:
                rp.allow_all = True
            self.parsers[domain] = rp
        return self.parsers[domain].can_fetch(self.user_agent, url)


class CrawlerEngine:
    """Run the same crawl loop against any source adapter."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.stats = {}

    def crawl(
        self,
        source: SourceAdapter,
        max_articles: int = 1,
        max_pages: int | None = None,
        max_depth: int | None = None,
        crawl_delay: float | None = None,
        timeout: int | None = None,
    ) -> List[Article]:
        page_limit = source.max_pages if max_pages is None else max_pages
        depth_limit = source.max_depth if max_depth is None else max_depth
        delay = source.crawl_delay if crawl_delay is None else crawl_delay
        request_timeout = source.request_timeout if timeout is None else timeout
        database.init_db(self.db_path)
        frontier = URLFrontier(max_depth=depth_limit)
        frontier.add_seeds(source.seed_urls)
        robots = RobotsManager(source.headers, request_timeout)
        session = requests.Session()
        session.headers.update(source.headers)
        articles: List[Article] = []
        pages_attempted = 0
        pages_crawled = 0
        failed_requests = 0
        skipped_robots = 0

        try:
            while (
                not frontier.is_empty()
                and pages_attempted < page_limit
                and len(articles) < max_articles
            ):
                item = frontier.get_next()
                if not item:
                    break

                current_url, current_depth = item
                if not source.is_allowed_url(current_url):
                    continue
                if not robots.is_allowed(current_url):
                    skipped_robots += 1
                    continue

                pages_attempted += 1
                started = time.time()
                status_code = None
                extracted_links: List[str] = []
                try:
                    response = session.get(
                        current_url,
                        timeout=request_timeout,
                    )
                    status_code = response.status_code
                    content_type = response.headers.get("Content-Type", "").lower()
                    is_html = (
                        "text/html" in content_type
                        or "application/xhtml" in content_type
                    )

                    if status_code == 200 and is_html:
                        html_content = source.prepare_html(response.text)
                        page_data = source.parse_page_data(
                            html_content,
                            current_url,
                            current_depth,
                            status_code,
                        )
                        database.insert_page(self.db_path, page_data)
                        pages_crawled += 1

                        if source.is_article_candidate(
                            current_url,
                            current_depth,
                            html_content,
                        ):
                            articles.append(self._to_article(source, page_data))

                        extracted_links = source.extract_links(
                            html_content,
                            current_url,
                        )
                        database.insert_links(
                            self.db_path,
                            current_url,
                            extracted_links,
                        )
                        if current_depth < depth_limit:
                            for link in extracted_links:
                                frontier.add_url(link, current_depth + 1)
                    else:
                        failed_requests += 1
                except requests.RequestException as error:
                    status_code = f"ERR ({type(error).__name__})"
                    failed_requests += 1

                elapsed = time.time() - started
                print(
                    f"[{source.name}] Depth {current_depth} | Status {status_code} | "
                    f"Links {len(extracted_links)} | {elapsed:.2f}s | {current_url}"
                )
                time.sleep(delay)
        finally:
            session.close()

        self.stats = {
            "source": source.name,
            "pages_attempted": pages_attempted,
            "pages_crawled": pages_crawled,
            "failed_requests": failed_requests,
            "skipped_robots": skipped_robots,
            "articles": len(articles),
        }
        return articles

    @staticmethod
    def _to_article(source: SourceAdapter, page_data: dict) -> Article:
        return Article(
            source=source.name,
            url=page_data.get("url", ""),
            title=page_data.get("title", "Untitled Page"),
            content=page_data.get("content", ""),
            depth=page_data.get("depth", 0),
            status_code=page_data.get("status_code", 0),
            crawled_at=page_data.get("crawled_at", ""),
            summary=page_data.get("summary", ""),
            author=page_data.get("author"),
            published_at=page_data.get("published_at"),
            category=page_data.get("category"),
        )
