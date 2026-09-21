"""
Focused Web Crawler Engine.
Tasks 3 & 9: Crawl Web Pages, Robots.txt Compliance, and Complete Crawling Pipeline.
"""
import time
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import requests

from config import (
    TOPIC, SEED_URLS, ALLOWED_DOMAINS,
    MAX_DEPTH, MAX_PAGES, REQUEST_TIMEOUT, CRAWL_DELAY,
    ARTICLES_ONLY, DB_PATH, DEFAULT_HEADERS,
    IGNORED_EXTENSIONS, IGNORED_SCHEMES, IGNORED_PATHS
)
import database
from url_frontier import URLFrontier
import parser

class RobotsManager:
    """Manages robots.txt caching and URL fetch permission checks."""
    def __init__(self, headers: Dict[str, str], timeout: int = 5):
        self.headers = headers
        self.user_agent = headers.get("User-Agent", "*")
        self.timeout = timeout
        self.parsers: Dict[str, RobotFileParser] = {}

    def is_allowed(self, url: str) -> bool:
        """Check if the given URL is allowed to be crawled by robots.txt."""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        if domain not in self.parsers:
            rp = RobotFileParser()
            robots_url = f"{parsed.scheme}://{domain}/robots.txt"
            try:
                resp = requests.get(robots_url, headers=self.headers, timeout=self.timeout)
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                else:
                    # If robots.txt returns 404 or other code, standard practice is allow
                    rp.allow_all = True
            except Exception:
                # If network fails fetching robots.txt, default to allow
                rp.allow_all = True
            self.parsers[domain] = rp

        return self.parsers[domain].can_fetch(self.user_agent, url)

class FocusedCrawler:
    """
    Main BFS Web Crawler coordinating Frontier, Fetcher, Parser, and Database.
    """
    def __init__(
        self,
        seed_urls: List[str] = SEED_URLS,
        allowed_domains: List[str] = ALLOWED_DOMAINS,
        max_depth: int = MAX_DEPTH,
        max_pages: int = MAX_PAGES,
        crawl_delay: float = CRAWL_DELAY,
        timeout: int = REQUEST_TIMEOUT,
        articles_only: bool = ARTICLES_ONLY,
        db_path: str = DB_PATH
    ):
        self.seed_urls = seed_urls
        self.allowed_domains = allowed_domains
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.crawl_delay = crawl_delay
        self.timeout = timeout
        self.articles_only = articles_only
        self.db_path = db_path
        
        self.frontier = URLFrontier(max_depth=self.max_depth)
        self.robots_manager = RobotsManager(headers=DEFAULT_HEADERS, timeout=self.timeout)
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        
        # Runtime statistics
        self.pages_crawled = 0
        self.failed_requests = 0
        self.skipped_robots = 0

    def start(self) -> None:
        """Run the complete crawling loop."""
        # 1. Initialize SQLite Database (Task 8)
        database.init_db(self.db_path)
        
        # 2. Add Seed URLs to URL Frontier (Task 1 & 2)
        self.frontier.add_seeds(self.seed_urls)
        
        crawl_counter = 0

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
                    
            except requests.RequestException as e:
                elapsed_time = time.time() - start_time
                status_code = "ERR"
                self.failed_requests += 1

            # Log current page crawl details as specified by the assignment
            print(f"[Crawl #{crawl_counter:03d}]")
            print(f"Depth : {current_depth}")
            print(f"URL   : {current_url}")
            print(f"Status: {status_code}")
            print(f"Title : {title if title else '(None)'}")
            print(f"Links : {len(extracted_links)} (articles only: {self.articles_only})")
            print(f"Time  : {elapsed_time:.2f} sec\n")
            
            # Respect crawl delay between requests (Task 3)
            time.sleep(self.crawl_delay)
