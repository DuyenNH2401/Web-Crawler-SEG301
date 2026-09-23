"""
Crawler chinh - Task 3 (gui HTTP request, xu ly loi, do response time),
Task 9 (vong lap crawl hoan chinh, tuan thu robots.txt), va loc noi dung
(chi luu bai viet that, bo trang loi/trang danh muc/trang qua ngan).
"""

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

    # ---------- Task: tuan thu robots.txt ----------
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
            rp = None  # khong doc duoc -> khong chan them, van log canh bao
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

    # ---------- Task 3: HTTP request + do thoi gian + bat loi ----------
    def _fetch(self, url, retries=1):
        """
        Thu request toi da (retries + 1) lan. Chi retry khi bi Timeout,
        vi day thuong la loi tam thoi do route mang cham, khong phai do
        URL sai hay bi chan han (ConnectionError/HTTPError thi khong retry).
        """
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

    # ---------- Task 9: vong lap crawl chinh ----------
    def crawl(self, seed_urls, max_pages):
        for url in seed_urls:
            normalized = normalize_url(url)
            if self.frontier.add_seed(normalized):
                self.stats["unique_urls_discovered"] += 1

        attempt_count = 0

        # Dieu kien dung: MAX_PAGES da dat HOAC Frontier rong (dung yeu cau Task 9)
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

            # Trang loi (404/403/500...) -> chi tinh vao thong ke Failed
            # Requests, KHONG luu vao pages (truoc day van luu ca dong
            # content rong, gay du lieu rac trong database).
            if status_code != 200:
                self.stats["failed_requests"] += 1
                time.sleep(config.CRAWL_DELAY)
                continue

            page_info, soup = extract_page_info(url, response.text, depth, status_code)

            # Luon trich link tu soup GOC de BFS di tiep, bat ke trang
            # nay co duoc luu vao pages hay khong (trang danh muc van can
            # duoc di qua de tim ra cac bai viet that ben trong no).
            links = extract_links(soup, url)
            for link in links:
                self.db.save_link(url, link)  # ghi lai TAT CA link phat hien (Task 8)
                if depth + 1 <= config.MAX_DEPTH:
                    if self.frontier.add(link, depth + 1):
                        self.stats["unique_urls_discovered"] += 1

            if page_info is None:
                # Khong khop ARTICLE_CONTENT_SELECTORS nao -> khong phai
                # bai viet that (vd trang danh muc/trang chu) -> bo qua.
                print(f"[SKIP-NOT-ARTICLE] {url}")
                self.stats["skipped_urls"] += 1
                time.sleep(config.CRAWL_DELAY)
                continue

            if len(page_info["content"]) < config.MIN_CONTENT_LENGTH:
                print(f"[SKIP-THIN] {url} -> content qua ngan "
                      f"({len(page_info['content'])} ky tu)")
                self.stats["skipped_urls"] += 1
                time.sleep(config.CRAWL_DELAY)
                continue

            self.db.save_page(page_info)
            self.stats["pages_crawled"] += 1

            time.sleep(config.CRAWL_DELAY)

        return self.stats
