import time
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

import config
from database import Database
from parser import extract_links, extract_page_info, is_allowed_domain, normalize_url
from url_frontier import URLFrontier


class Crawler:
    def __init__(self):
        self.frontier = URLFrontier()
        self.db = Database()
        self.session = requests.Session()
        self.session.headers.update(config.DEFAULT_HEADERS)

        self._robots_cache = {}  # netloc -> RobotFileParser (hoac None neu khong doc duoc)

        self.stats = {
            "pages_crawled": 0,
            "unique_urls_discovered": 0,
            "skipped_urls": 0,
            "failed_requests": 0,
        }

    def _get_robot_parser(self, url):
        parsed = urlparse(url)
        netloc = parsed.netloc
        if netloc in self._robots_cache:
            return self._robots_cache[netloc]

        robots_url = f"{parsed.scheme}://{netloc}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        try:
            rp.read()
        except Exception as e:
            print(f"[WARN] Khong doc duoc robots.txt cua {netloc}: {e}")
            rp = None
        self._robots_cache[netloc] = rp
        return rp

    def _can_fetch(self, url):
        rp = self._get_robot_parser(url)
        if rp is None:
            return True
        try:
            return rp.can_fetch(config.USER_AGENT, url)
        except Exception:
            return True

    def _fetch(self, url, retries=1):
        start = time.time()
        attempt = 0
        while True:
            try:
                response = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
                elapsed = time.time() - start
                return response, elapsed, None
            except requests.exceptions.Timeout as e:
                attempt += 1
                if attempt > retries:
                    elapsed = time.time() - start
                    return None, elapsed, str(e)
                time.sleep(1)  # cho 1 giay roi thu lai
            except requests.exceptions.RequestException as e:
                elapsed = time.time() - start
                return None, elapsed, str(e)

    def crawl(self, seed_urls, max_pages):
        for url in seed_urls:
            normalized = normalize_url(url)
            if self.frontier.add_seed(normalized):
                self.stats["unique_urls_discovered"] += 1

        attempt_count = 0

        while not self.frontier.is_empty() and self.stats["pages_crawled"] < max_pages:
            item = self.frontier.next_url()
            if item is None:
                break
            url, depth = item

            if self.frontier.is_visited(url):
                continue

            if not is_allowed_domain(url):
                self.stats["skipped_urls"] += 1
                continue

            if not self._can_fetch(url):
                print(f"[ROBOTS] Bi robots.txt chan, bo qua: {url}")
                self.stats["skipped_urls"] += 1
                self.frontier.mark_visited(url)
                continue

            self.frontier.mark_visited(url)
            attempt_count += 1

            response, elapsed, error = self._fetch(url)

            if error is not None:
                print(f"[FAIL #{attempt_count:03d}] {url} -> {error}")
                self.stats["failed_requests"] += 1
                time.sleep(config.CRAWL_DELAY)
                continue

            status_code = response.status_code
            print(f"[Crawl #{attempt_count:03d}] Depth {depth} | Status {status_code} | "
                  f"{elapsed:.2f}s | {url}")

            if status_code != 200:
                page_info = {
                    "url": url,
                    "domain": urlparse(url).netloc,
                    "title": "",
                    "content": "",
                    "depth": depth,
                    "status_code": status_code,
                    "crawled_at": datetime.now(timezone.utc).isoformat(),
                }
                self.db.save_page(page_info)
                self.stats["failed_requests"] += 1
                time.sleep(config.CRAWL_DELAY)
                continue

            page_info, soup = extract_page_info(url, response.text, depth, status_code)
            self.db.save_page(page_info)
            self.stats["pages_crawled"] += 1

            links = extract_links(soup, url)
            for link in links:
                self.db.save_link(url, link)
                if depth + 1 <= config.MAX_DEPTH:
                    if self.frontier.add(link, depth + 1):
                        self.stats["unique_urls_discovered"] += 1

            time.sleep(config.CRAWL_DELAY)

        return self.stats
