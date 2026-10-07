"""Client gửi request tới Reddit bằng cookie (hỗ trợ cả JSON và HTML)."""
from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

from .parser import parse_comments, parse_posts

USER_AGENT = "linux:reddit-crawler:v0.1.0"
BROWSER_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0"


class RedditClient:
    """Đọc dữ liệu bài viết và comment từ Reddit qua cookie bằng JSON hoặc HTML."""

    def __init__(self, cookies_file: Path | str, *, user_agent: str = USER_AGENT,
                 request_delay: float = 2.0, timeout: float = 30.0):
        raw = Path(cookies_file).read_text(encoding="utf-8").strip()
        self.cookie = raw.removeprefix("Cookie:").removeprefix("cookie:").strip()
        if not self.cookie:
            raise ValueError("File cookie rỗng")
        self.user_agent = user_agent
        self.request_delay = request_delay
        self.timeout = timeout
        self.last_request = 0.0

    def _wait_rate_limit(self) -> None:
        wait = (self.last_request + self.request_delay) - time.time()
        if wait > 0:
            time.sleep(wait)
        self.last_request = time.time()

    def _get(self, path: str, **params: Any) -> Any:
        self._wait_rate_limit()
        url = f"https://www.reddit.com{path}.json"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={
            "Cookie": self.cookie,
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        })
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503) and attempt < 2:
                    try:
                        delay = float(e.headers.get("Retry-After", 2 ** attempt))
                    except (ValueError, TypeError):
                        delay = float(2 ** attempt)
                    time.sleep(delay)
                    continue
                raise ValueError(f"Reddit HTTP {e.code}") from None
            except Exception as e:
                if attempt == 2:
                    raise ValueError(f"Lỗi mạng: {e}") from None
                time.sleep(1.0)

    def _get_html(self, path_or_url: str) -> str:
        self._wait_rate_limit()
        # Chuẩn hóa và mã hóa URL nếu có chứa ký tự tiếng Việt có dấu
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            parsed = urllib.parse.urlparse(path_or_url)
            safe_path = urllib.parse.quote(parsed.path, safe="/:?=&%#")
            url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, safe_path, parsed.params, parsed.query, parsed.fragment))
        else:
            safe_path = urllib.parse.quote(path_or_url, safe="/:?=&%#")
            url = f"https://www.reddit.com{safe_path}"

        ua = BROWSER_USER_AGENT if self.user_agent == USER_AGENT else self.user_agent
        req = urllib.request.Request(url, headers={
            "Cookie": self.cookie,
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return resp.read().decode("utf-8", errors="ignore")
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503) and attempt < 2:
                    try:
                        delay = float(e.headers.get("Retry-After", 2 ** attempt))
                    except (ValueError, TypeError):
                        delay = float(2 ** attempt)
                    time.sleep(delay)
                    continue
                raise ValueError(f"Reddit HTTP {e.code}") from None
            except Exception as e:
                if attempt == 2:
                    raise ValueError(f"Lỗi mạng: {e}") from None
                time.sleep(1.0)
        return ""

    def new_posts(self, subreddit: str, *, limit: int = 100) -> list[str]:
        sub = subreddit.lower().removeprefix("r/")
        data = self._get(f"/r/{sub}/new", limit=min(limit, 100), raw_json=1)
        return parse_posts(data)

    def comments(self, subreddit: str, post_id: str) -> tuple[list[dict[str, Any]], int]:
        sub = subreddit.lower().removeprefix("r/")
        data = self._get(f"/r/{sub}/comments/{post_id}", limit=500, sort="new", raw_json=1)
        return parse_comments(data, sub)

    def new_posts_html(self, subreddit: str, *, limit: int = 100) -> list[dict[str, Any]]:
        sub = subreddit.removeprefix("r/").removeprefix("R/")
        html = self._get_html(f"/r/{sub}/new/")
        from .html_parser import parse_posts_html
        posts = parse_posts_html(html)
        return posts[:limit]

    def comments_html(self, subreddit: str, post_id: str,
                      permalink: str | None = None) -> tuple[list[dict[str, Any]], int]:
        sub = subreddit.removeprefix("r/").removeprefix("R/")
        path = permalink if permalink else f"/r/{sub}/comments/{post_id}/"
        html = self._get_html(path)
        from .html_parser import parse_comments_html
        return parse_comments_html(html, sub)
