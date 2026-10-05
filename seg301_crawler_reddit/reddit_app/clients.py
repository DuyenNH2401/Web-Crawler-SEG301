"""Client JSON/cookie và client API PRAW cho cùng giao diện thu thập."""
from __future__ import annotations

from collections import deque
from contextlib import closing
from http.cookiejar import Cookie, CookieJar, DefaultCookiePolicy
from http.cookies import CookieError, SimpleCookie
import json
import os
from pathlib import Path
import re
import time
from types import SimpleNamespace
from typing import Any, Callable, Iterable
import urllib.error
import urllib.parse
import urllib.request

from .config import (
    DEFAULT_REQUEST_DELAY, DEFAULT_TIMEOUT, DELETED, LOG,
    MAX_COMMENTS_PER_RESPONSE, MAX_COOKIE_HEADER_CHARS, MAX_POSTS_PER_PAGE,
    MAX_RESPONSE_BYTES, PUBLIC_USER_AGENT,
)
from .models import Comment, subreddit_name
from .network import network_error_message, request_with_backoff
from .progress import CrawlProgress


def load_session_cookies(path: Path) -> CookieJar:
    """Read a local request Cookie header, without echoing or persisting values."""
    try:
        with Path(path).open(encoding="utf-8") as source:
            raw = source.read(MAX_COOKIE_HEADER_CHARS + 1).strip()
    except UnicodeError:
        raise ValueError("file cookie phải là văn bản UTF-8 chứa một dòng Cookie request header") from None
    if not raw or len(raw) > MAX_COOKIE_HEADER_CHARS:
        raise ValueError("file cookie rỗng hoặc quá lớn")
    if raw.lower().startswith("cookie:"):
        raw = raw[7:].strip()
    if any(ord(char) < 32 or ord(char) > 126 for char in raw):
        raise ValueError("file cookie phải chứa một dòng Cookie request header ASCII")
    parsed = SimpleCookie()
    try:
        parsed.load(raw)
    except CookieError:
        raise ValueError("Cookie request header không hợp lệ; xem hướng dẫn trong README") from None
    if not parsed:
        raise ValueError("không tìm thấy cookie hợp lệ trong file; xem hướng dẫn trong README")
    policy = DefaultCookiePolicy(strict_ns_domain=DefaultCookiePolicy.DomainStrictNonDomain)
    jar = CookieJar(policy=policy)
    for name, morsel in parsed.items():
        if any(ord(char) < 32 or ord(char) > 126 for char in morsel.value):
            raise ValueError("Cookie request header chứa giá trị không hợp lệ")
        jar.set_cookie(Cookie(version=0, name=name, value=morsel.coded_value,
                              port=None, port_specified=False,
                              domain="www.reddit.com", domain_specified=False, domain_initial_dot=False,
                              path="/", path_specified=True, secure=True, expires=None,
                              discard=True, comment=None, comment_url=None, rest={}))
    return jar


class PublicReddit:
    """Read Reddit JSON with an optional session opener; stop on access errors."""

    def __init__(self, *, user_agent: str = PUBLIC_USER_AGENT,
                 request_delay: float = DEFAULT_REQUEST_DELAY, timeout: float = DEFAULT_TIMEOUT,
                 comment_limit: int = MAX_COMMENTS_PER_RESPONSE,
                 opener: Callable[..., Any] | None = None,
                 sleep: Callable[[float], None] = time.sleep, progress: CrawlProgress | None = None):
        self.user_agent = user_agent
        self.request_delay = request_delay
        self.timeout = timeout
        self.comment_limit = min(comment_limit, MAX_COMMENTS_PER_RESPONSE)
        self.opener = opener or urllib.request.urlopen
        self.sleep = sleep
        self.progress = progress
        self.next_request_at = 0.0
        self.name = ""

    def close(self) -> None:
        pass

    def subreddit(self, name: str) -> PublicReddit:
        self.name = subreddit_name(name)
        return self

    def _get(self, path: str, **params: Any) -> Any:
        url = "https://www.reddit.com" + path + "?" + urllib.parse.urlencode(params)
        if self.progress is not None:
            self.progress.update(stage=f"Đang lấy JSON {path}")

        def send() -> Any:
            wait = self.next_request_at - time.monotonic()
            if wait > 0:
                self.sleep(wait)
            self.next_request_at = time.monotonic() + self.request_delay
            request = urllib.request.Request(url, headers={"User-Agent": self.user_agent,
                                                         "Accept": "application/json"})
            LOG.info("request start method=GET host=www.reddit.com path=%s timeout_seconds=%s",
                     path, self.timeout)
            try:
                response = self.opener(request, timeout=self.timeout)
            except urllib.error.HTTPError as error:
                response = error
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                raise ValueError(network_error_message(error)) from None
            # Adapt urllib responses to the shared bounded HTTP retry helper.
            return SimpleNamespace(status_code=response.status, headers=response.headers,
                                   close=response.close, response=response)

        response = request_with_backoff(send, sleep=self.sleep)
        with closing(response.response) as stream:
            if response.status_code != 200:
                raise ValueError(f"Reddit trả HTTP {response.status_code}; dừng truy cập endpoint Reddit")
            try:
                raw = stream.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ValueError
                return json.loads(raw)
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                raise ValueError(network_error_message(error)) from None
            except (ValueError, UnicodeError):
                raise ValueError("Reddit không trả JSON hợp lệ hoặc response quá lớn") from None

    @staticmethod
    def children(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, dict) or not isinstance(value.get("data"), dict):
            raise ValueError("Reddit trả listing JSON không hợp lệ")
        children = value["data"].get("children")
        if not isinstance(children, list) or any(not isinstance(child, dict) for child in children):
            raise ValueError("Reddit trả children JSON không hợp lệ")
        return children

    def new(self, *, limit: int) -> Iterable[Any]:
        name = self.name
        after = None
        cursors = set()
        count = 0
        while count < limit:
            params = dict(limit=min(MAX_POSTS_PER_PAGE, limit - count), raw_json=1)
            if after:
                params["after"] = after
            page = self._get(f"/r/{name}/new.json", **params)
            children = self.children(page)
            for child in children:
                if child.get("kind") != "t3":
                    continue
                pid = child.get("data", {}).get("id")
                if not isinstance(pid, str) or not re.fullmatch(r"[a-z0-9]+", pid):
                    raise ValueError("Reddit trả post ID không hợp lệ")
                yield SimpleNamespace(id=pid, comments=PublicForest(self, name, pid))
                count += 1
                if count >= limit:
                    return
            after = page["data"].get("after")
            if not children or not after:
                break
            if not isinstance(after, str) or after in cursors:
                raise ValueError("Reddit trả cursor phân trang không hợp lệ/lặp lại")
            cursors.add(after)


class PublicForest:
    def __init__(self, client: PublicReddit, subreddit: str, post_id: str):
        self.client = client
        self.subreddit = subreddit
        self.post_id = post_id
        self.comments: list[Comment] = []
        self.remaining: list[Any] = []
        self.loaded = False

    def replace_more(self, *, limit: int) -> list[Any]:
        if limit != 0:
            raise ValueError("chế độ public chỉ đọc comment được trả về, more_limit phải là 0")
        if not self.loaded:
            payload = self.client._get(f"/r/{self.subreddit}/comments/{self.post_id}.json",
                                       limit=self.client.comment_limit, sort="new", raw_json=1)
            if not isinstance(payload, list) or len(payload) < 2:
                raise ValueError("Reddit trả comment JSON không hợp lệ")
            pending = deque(self.client.children(payload[1]))
            while pending:
                child = pending.popleft()
                if child.get("kind") == "more":
                    self.remaining.append(child)
                    continue
                if child.get("kind") != "t1" or not isinstance(child.get("data"), dict):
                    raise ValueError("Reddit trả comment JSON không hợp lệ")
                raw = child["data"]
                author = raw.get("author")
                author_id = raw.get("author_fullname") if author and author not in DELETED else None
                if isinstance(author_id, str):
                    author_id = author_id.removeprefix("t2_")
                permalink = raw.get("permalink")
                if isinstance(permalink, str) and permalink.startswith("/"):
                    permalink = "https://www.reddit.com" + permalink
                self.comments.append(Comment.from_value(dict(
                    comment_id=raw.get("id"), content=raw.get("body"), author_id=author_id,
                    author_name=author if author and author not in DELETED else None,
                    parent_id=raw.get("parent_id"), post_id=raw.get("link_id"),
                    comment_url=permalink, created_at=raw.get("created_utc"),
                    like_count=raw.get("score"), subreddit=raw.get("subreddit") or self.subreddit)))
                replies = raw.get("replies")
                if replies:
                    pending.extend(self.client.children(replies))
            self.loaded = True
        return self.remaining

    def list(self) -> list[Comment]:
        return self.comments


def session_client(path: Path, **options: Any) -> PublicReddit:
    jar = load_session_cookies(path)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    return PublicReddit(opener=opener.open, **options)


def api_client() -> Any:
    keys = ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT")
    missing = [key for key in keys if not os.environ.get(key, "").strip()]
    if missing:
        raise ValueError("thiếu biến môi trường: " + ", ".join(missing) +
                         "; nghiên cứu: xem Reddit for Researchers trong README")
    try:
        import praw
        from prawcore import Requestor
    except ImportError:
        raise ValueError("chưa cài PRAW; chạy pip install -r requirements.txt") from None

    class LoggedRequestor(Requestor):
        def request(self, *args: Any, **kwargs: Any) -> Any:
            # PRAW/prawcore also pace by rate-limit headers and retry network errors.
            # Never log URLs, headers, credentials or response bodies.
            kwargs["timeout"] = (10, 30)
            start = time.monotonic()
            try:
                return request_with_backoff(lambda: super(LoggedRequestor, self).request(*args, **kwargs))
            except Exception as exc:
                LOG.warning("request failed=%s elapsed_ms=%d", type(exc).__name__,
                            (time.monotonic() - start) * 1000)
                raise

    client = praw.Reddit(client_id=os.environ[keys[0]], client_secret=os.environ[keys[1]],
                         user_agent=os.environ[keys[2]], requestor_class=LoggedRequestor,
                         check_for_updates=False, timeout=30)
    client.read_only = True
    return client
