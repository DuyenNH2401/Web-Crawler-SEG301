"""
crawler.py - Tasks 3, 6, 9 and the crawling statistics.

Ties the frontier, the fetcher, the parser and the database together into one
breadth-first crawl.
"""

import hashlib
import time
from collections import Counter
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

import config
import parser as page_parser
from database import Database
from url_frontier import URLFrontier


class Crawler:
    def __init__(self, fresh=True):
        self.frontier = URLFrontier()
        self.db = Database(config.DATABASE_PATH)
        if fresh:
            self.db.clear()

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.USER_AGENT})

        self._robots = {}          # host -> RobotFileParser
        self._content_hashes = set()
        self._last_request_at = 0.0

        self.stats = {
            "pages_crawled": 0,
            "urls_discovered": 0,
            "skipped_urls": 0,
            "failed_requests": 0,
            "duplicate_content": 0,
            "max_depth_reached": 0,
            "by_depth": Counter(),
            "by_status": Counter(),
            "skip_reasons": Counter(),
            "failure_reasons": Counter(),
            "started_at": None,
            "finished_at": None,
        }

    # ------------------------------------------------------------ robots --
    def may_fetch(self, url):
        """Task 9 hint - respect robots.txt. Unreachable robots.txt = allowed."""
        if not config.RESPECT_ROBOTS:
            return True

        parts = urlparse(url)
        host = parts.netloc
        if host not in self._robots:
            rp = RobotFileParser()
            rp.set_url(f"{parts.scheme}://{host}/robots.txt")
            try:
                rp.read()
            except Exception:
                rp = None
            self._robots[host] = rp

        rp = self._robots[host]
        if rp is None:
            return True
        try:
            return rp.can_fetch(config.USER_AGENT, url)
        except Exception:
            return True

    # ----------------------------------------------------------- fetching --
    def _wait_for_delay(self):
        elapsed = time.time() - self._last_request_at
        if elapsed < config.CRAWL_DELAY:
            time.sleep(config.CRAWL_DELAY - elapsed)

    def fetch(self, url):
        """
        Task 3 - download one page.

        Returns (response, elapsed_seconds) on success, or (None, error) on
        failure. A non-200 response is still returned, so the status code can
        be counted.
        """
        self._wait_for_delay()
        start = time.time()
        try:
            response = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
        except requests.Timeout:
            self._last_request_at = time.time()
            return None, "Timeout"
        except requests.ConnectionError:
            self._last_request_at = time.time()
            return None, "ConnectionError"
        except requests.RequestException as error:
            self._last_request_at = time.time()
            return None, type(error).__name__
        self._last_request_at = time.time()

        # requests guesses latin-1 when the server sends no charset; fall back
        # to the encoding sniffed from the bytes instead.
        if response.encoding is None:
            response.encoding = response.apparent_encoding

        return response, time.time() - start

    # ------------------------------------------------------------- crawl --
    def crawl(self):
        self.stats["started_at"] = time.time()
        self.frontier.add_seeds(config.SEED_URLS)
        self.stats["urls_discovered"] = len(self.frontier.seen)

        print("-" * 60)

        stopped_early = False
        while not self.frontier.is_empty():
            if self.stats["pages_crawled"] >= config.MAX_PAGES:
                print(f"\nStopping: MAX_PAGES ({config.MAX_PAGES}) reached.")
                stopped_early = True
                break

            url, depth = self.frontier.next()

            # Task 7 - never fetch the same URL twice.
            if self.frontier.has_visited(url):
                self.stats["skipped_urls"] += 1
                self.stats["skip_reasons"]["already visited"] += 1
                continue

            if not self.may_fetch(url):
                self.stats["skipped_urls"] += 1
                self.stats["skip_reasons"]["robots.txt"] += 1
                print(f"  SKIP (robots.txt): {url}")
                continue

            self.frontier.mark_visited(url)
            self._crawl_one(url, depth)

        if not stopped_early:
            print("\nStopping: URL frontier is empty.")

        self.stats["finished_at"] = time.time()

    def _crawl_one(self, url, depth):
        response, result = self.fetch(url)
        next_number = self.stats["pages_crawled"] + 1

        if response is None:
            self.stats["failed_requests"] += 1
            self.stats["failure_reasons"][result] += 1
            print(f"\n[Crawl #{next_number:03d}]  FAILED")
            print(f"Depth : {depth}")
            print(f"URL   : {url}")
            print(f"Error : {result}")
            return

        elapsed = result
        self.stats["by_status"][response.status_code] += 1

        if response.status_code != 200:
            self.stats["failed_requests"] += 1
            self.stats["failure_reasons"][f"HTTP {response.status_code}"] += 1
            print(f"\n[Crawl #{next_number:03d}]  HTTP {response.status_code}")
            print(f"Depth : {depth}")
            print(f"URL   : {url}")
            print(f"Time  : {elapsed:.2f} sec")
            return

        if "html" not in response.headers.get("Content-Type", "").lower():
            self.stats["skipped_urls"] += 1
            self.stats["skip_reasons"]["not HTML"] += 1
            return

        soup = page_parser.make_soup(response.text)

        # Extract links before extract_page_data(), which strips noise tags.
        valid_urls, all_urls, rejected = page_parser.extract_links(soup, url)
        page = page_parser.extract_page_data(soup, url, depth, response.status_code)

        # Task 7 - a second copy of the same text under a different URL.
        checksum = hashlib.md5(page["content"].encode("utf-8")).hexdigest()
        if checksum in self._content_hashes:
            self.stats["duplicate_content"] += 1
            self.stats["skipped_urls"] += 1
            self.stats["skip_reasons"]["duplicate content"] += 1
            print(f"  SKIP (duplicate content): {url}")
            return
        self._content_hashes.add(checksum)

        # Task 8 - store.
        self.db.save_page(page)
        self.db.save_links(url, all_urls)

        self.stats["pages_crawled"] += 1
        self.stats["by_depth"][depth] += 1
        self.stats["max_depth_reached"] = max(self.stats["max_depth_reached"], depth)

        title = page["title"][:70] or "(no title)"
        print(f"\n[Crawl #{self.stats['pages_crawled']:03d}]")
        print(f"Depth : {depth}")
        print(f"URL   : {url}")
        print(f"Status: {response.status_code}")
        print(f"Title : {title}")
        print(f"Links : {len(valid_urls)} valid / {len(all_urls)} found")
        print(f"Time  : {elapsed:.2f} sec")

        for _, reason in rejected:
            self.stats["skip_reasons"][reason] += 1
        self.stats["skipped_urls"] += len(rejected)

        # Task 6 - depth control.
        new_depth = depth + 1
        if new_depth > config.MAX_DEPTH:
            return
        if config.MAX_LINKS_PER_PAGE:
            valid_urls = valid_urls[:config.MAX_LINKS_PER_PAGE]
        for link in valid_urls:
            if self.frontier.add(link, new_depth):
                self.stats["urls_discovered"] += 1

    # -------------------------------------------------------- statistics --
    def print_summary(self):
        """Section 14 - every number below is computed from the crawl."""
        stats = self.stats
        duration = (stats["finished_at"] or time.time()) - stats["started_at"]

        print()
        print("=" * 41)
        print("           CRAWLING SUMMARY")
        print("=" * 41)
        print(f"Topic                  : {config.TOPIC}")
        print(f"Domains                : {', '.join(config.DOMAINS)}")
        print(f"Seed URLs              : {len(config.SEED_URLS)}")
        print(f"Pages Crawled          : {stats['pages_crawled']}")
        print(f"Unique URLs Discovered : {stats['urls_discovered']}")
        print(f"Skipped URLs           : {stats['skipped_urls']}")
        print(f"Failed Requests        : {stats['failed_requests']}")
        print(f"Duplicate Content      : {stats['duplicate_content']}")
        print(f"Maximum Depth          : {stats['max_depth_reached']} (limit {config.MAX_DEPTH})")
        print(f"Frontier Remaining     : {len(self.frontier)}")
        print(f"Total Time             : {duration:.1f} seconds")

        print("-" * 41)
        for depth in sorted(stats["by_depth"]):
            print(f"Depth {depth}                : {stats['by_depth'][depth]} pages")

        print("-" * 41)
        for status in sorted(stats["by_status"]):
            print(f"HTTP {status}               : {stats['by_status'][status]}")

        if stats["failure_reasons"]:
            print("-" * 41)
            print("Failure reasons:")
            for reason, count in stats["failure_reasons"].most_common():
                print(f"  {reason:<22}: {count}")

        print("-" * 41)
        print("Skip reasons:")
        for reason, count in stats["skip_reasons"].most_common():
            print(f"  {reason:<22}: {count}")

        print("-" * 41)
        print("Pages stored per domain:")
        for domain, count in self.db.pages_per_domain():
            print(f"  {domain:<22}: {count}")

        print("-" * 41)
        print(f"Database               : {config.DATABASE_PATH}")
        print(f"  pages rows           : {self.db.count_pages()}")
        print(f"  links rows           : {self.db.count_links()}")
        print("=" * 41)

    def close(self):
        self.db.close()
        self.session.close()
