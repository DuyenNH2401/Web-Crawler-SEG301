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

<<<<<<< HEAD
        # 3. Main Crawling Loop (Task 9)
        while not self.frontier.is_empty() and self.pages_crawled < self.max_pages:
            next_item = self.frontier.get_next()
            if not next_item:
                break
                
            current_url, current_depth = next_item
            
            # Check robots.txt constraint
            if not self.robots_manager.is_allowed(current_url):
                self.skipped_robots += 1
                continue
                
            crawl_counter += 1
            start_time = time.time()
            status_code = None
            html_text = None
            title = ""
            extracted_links: List[str] = []
            error_message = ""
            
            try:
                # HTTP Request with timeout (Task 3)
                response = self.session.get(current_url, timeout=self.timeout)
                status_code = response.status_code
                elapsed_time = time.time() - start_time
                
                # Check for HTML content type
                content_type = response.headers.get("Content-Type", "").lower()
                is_html = "text/html" in content_type or "application/xhtml" in content_type
                
                if status_code == 200 and is_html:
                    html_text = response.text
                    
                    # 4. Extract page metadata and visible text (Task 4)
                    page_data = parser.parse_page_data(
                        html_content=html_text,
                        url=current_url,
                        depth=current_depth,
                        status_code=status_code
                    )
                    title = page_data.get("title", "")
                    
                    # 5. Store page in SQLite (Task 8)
                    database.insert_page(self.db_path, page_data)
                    self.pages_crawled += 1
                    
                    # 6. Extract and filter hyperlinks (Task 5)
                    # Chỉ chấp nhận link bài báo (.html) nếu bật articles_only
                    extracted_links = parser.extract_and_filter_links(
                        html_content=html_text,
                        current_url=current_url,
                        allowed_domains=self.allowed_domains,
                        ignored_extensions=IGNORED_EXTENSIONS,
                        ignored_schemes=IGNORED_SCHEMES,
                        ignored_paths=IGNORED_PATHS,
                        articles_only=self.articles_only
                    )
                    
                    # 7. Store links in SQLite (Task 8)
                    database.insert_links(self.db_path, current_url, extracted_links)
                    
                    # 8. Add discovered valid URLs to Frontier with next depth (Task 6 & 7)
                    if current_depth < self.max_depth:
                        for link in extracted_links:
                            self.frontier.add_url(link, depth=current_depth + 1)
                else:
                    # Non-200 or non-HTML response
                    self.failed_requests += 1
                    if status_code != 200:
                        error_message = f"HTTP {status_code}"
                    else:
                        error_message = f"Unsupported Content-Type: {content_type or '(missing)'}"
                    
            except requests.RequestException as e:
                elapsed_time = time.time() - start_time
                status_code = "ERR"
                self.failed_requests += 1
                error_message = f"{type(e).__name__}: {e}"

            # Log current page crawl details as specified by the assignment
            print(f"[Crawl #{crawl_counter:03d}]")
            print(f"Depth : {current_depth}")
            print(f"URL   : {current_url}")
            print(f"Status: {status_code}")
            print(f"Title : {title if title else '(None)'}")
            link_mode = (
                "articles only"
                if self.articles_only
                else "content pages; media/utility excluded"
            )
            print(f"Links : {len(extracted_links)} ({link_mode})")
            if error_message:
                print(f"Error : {error_message}")
            print(f"Time  : {elapsed_time:.2f} sec\n")
            
            # Respect crawl delay between requests (Task 3)
            time.sleep(self.crawl_delay)
=======
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
>>>>>>> 73c7225514e14883d3bf6cd6a00bb4611de504c1
