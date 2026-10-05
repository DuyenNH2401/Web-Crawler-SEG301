"""Collect replies visible in an X browser session."""

import json
import os
from datetime import datetime, timezone
from urllib.parse import urlparse

from models import Comment
from .x import parse_post_id


# Read rendered post cards only. No internal X requests.
VISIBLE_POSTS_JS = """articles => articles.map(article => {
    const time = article.querySelector('time');
    const link = time && time.closest('a');
    const text = article.querySelector('[data-testid="tweetText"]');
    const name = article.querySelector('[data-testid="User-Name"] span');
    return {
        url: link ? link.href : '',
        created_at: time ? time.getAttribute('datetime') : '',
        content: text ? text.innerText : '',
        author_name: name ? name.innerText : ''
    };
})"""


def _visible_post_id(raw: dict) -> str | None:
    try:
        return parse_post_id(raw.get("url") or "")
    except ValueError:
        return None


def browser_post_url(post: str) -> str:
    """Keep the supplied permalink path after validating it is an X post."""
    post = post.strip()
    post_id = parse_post_id(post)
    if post.isdigit():
        return f"https://x.com/i/web/status/{post_id}"
    return f"https://x.com/{urlparse(post).path.strip('/')}"


def load_cookies(path: str) -> list[dict]:
    """Read local X session cookies without printing their values."""
    with open(path, encoding="utf-8") as source:
        values = json.load(source)
    if not isinstance(values, dict):
        raise ValueError("Cookie file must be a JSON object")
    cookies = []
    for name in ("auth_token", "ct0"):
        value = values.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Cookie file is missing {name}")
        cookies.append({
            "name": name,
            "value": value.strip(),
            "domain": ".x.com",
            "path": "/",
            "secure": True,
            "httpOnly": name == "auth_token",
        })
    return cookies


class SessionRejectedError(RuntimeError):
    """X removed the session cookies after navigation."""


def map_visible_reply(raw: dict, root_id: str, collected_at: str) -> Comment | None:
    """Map a rendered post card, leaving unavailable metadata explicit."""
    url = raw.get("url") or ""
    try:
        comment_id = _visible_post_id(raw)
        if comment_id is None:
            return None
        if comment_id == root_id:
            return None
        created_at = datetime.fromisoformat(
            (raw.get("created_at") or "").replace("Z", "+00:00")
        )
        if created_at.tzinfo is None:
            return None
    except (ValueError, TypeError):
        return None
    content = (raw.get("content") or "").strip()
    if not content:
        return None
    username = urlparse(url).path.strip("/").split("/")[0]
    if username == "i":
        username = ""
    created_at = created_at.astimezone(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")
    return Comment(
        platform="x", comment_id=comment_id, content=content,
        author_id="UNKNOWN", author_name=(raw.get("author_name") or username or "UNKNOWN").strip(),
        parent_id="UNKNOWN", post_id=root_id,
        comment_url=(f"https://x.com/{username}/status/{comment_id}" if username
                     else f"https://x.com/i/web/status/{comment_id}"),
        created_at=created_at, like_count=0, collected_at=collected_at,
    )


class XBrowserCrawler:
    """Use Chromium with a local login profile or supplied session cookies."""

    def __init__(self, profile_dir: str, *, cookie_file: str | None = None,
                 headless: bool = False, browser_channel: str = "chrome"):
        cookies = load_cookies(cookie_file) if cookie_file and os.path.exists(cookie_file) else []
        self.headless = headless
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as error:
            raise RuntimeError(
                "Install browser support: python -m pip install -r requirements.txt"
            ) from error
        os.makedirs(profile_dir, exist_ok=True)
        self.playwright = sync_playwright().start()
        try:
            self.context = self.playwright.chromium.launch_persistent_context(
                profile_dir, headless=headless, channel=browser_channel
            )
            profile_has_session = self._session_cookies_present()
            if cookies and not profile_has_session:
                self.context.add_cookies(cookies)
            self._session_expected = profile_has_session or bool(cookies)
        except Exception as error:
            if hasattr(self, "context"):
                self.context.close()
            self.playwright.stop()
            if "Executable doesn't exist" in str(error):
                raise RuntimeError(
                    f"Browser {browser_channel} was not found. Install it or use --browser-channel chromium after running python -m playwright install chromium"
                ) from error
            raise
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        self._ready = self._session_expected

    def crawl(self, post: str, *, max_comments: int = 1000,
              max_scrolls: int = 30) -> list[Comment]:
        post_id = parse_post_id(post)
        if max_comments < 1 or max_scrolls < 1:
            raise ValueError("max_comments and max_scrolls must be at least 1")
        post_url = browser_post_url(post)
        if self.headless and not self._ready:
            raise RuntimeError("No X login session is available. Run without --headless and sign in.")
        try:
            self._open_post(post_url)
        except SessionRejectedError:
            if self.headless:
                raise RuntimeError(
                    "X rejected the saved login session. Run without --headless "
                    "and sign in through the opened window."
                ) from None
            self._session_expected = False
            self._ready = False
            print("X rejected the saved cookies. Sign in in the opened Chrome window.")
        if not self._ready:
            try:
                input("Đăng nhập X trong cửa sổ vừa mở, rồi nhấn Enter tại đây... ")
            except EOFError as error:
                raise RuntimeError("Run browser mode in an interactive terminal") from error
            if not self._session_cookies_present():
                raise RuntimeError("X login is not complete in the opened browser window")
            self._session_expected = True
            self._ready = True
            self._open_post(post_url)
        try:
            self.page.locator('article[data-testid="tweet"]').first.wait_for(timeout=15000)
        except Exception as error:
            raise RuntimeError(
                "No X post is visible. Check login and the post URL in the browser."
            ) from error
        visible = self.page.locator('article[data-testid="tweet"]').evaluate_all(
            VISIBLE_POSTS_JS
        )
        if not any(_visible_post_id(raw) == post_id for raw in visible):
            raise RuntimeError("The requested post is not visible in the browser")

        collected_at = datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        ).replace("+00:00", "Z")
        found: dict[str, Comment] = {}
        unchanged = 0
        for _ in range(max_scrolls):
            before = len(found)
            raw_posts = self.page.locator('article[data-testid="tweet"]').evaluate_all(
                VISIBLE_POSTS_JS
            )
            for raw in raw_posts:
                comment = map_visible_reply(raw, post_id, collected_at)
                if comment:
                    found[comment.comment_id] = comment
                    if len(found) >= max_comments:
                        break
            if len(found) >= max_comments:
                break
            unchanged = unchanged + 1 if len(found) == before else 0
            if unchanged >= 3:
                break
            self.page.evaluate("window.scrollBy(0, window.innerHeight * 0.85)")
            self.page.wait_for_timeout(1200)
        return list(found.values())

    def _open_post(self, post_url: str) -> None:
        try:
            response = self.page.goto(post_url, wait_until="domcontentloaded")
        except Exception as error:
            if self._session_expected and not self._session_cookies_present():
                raise SessionRejectedError(
                    "X did not retain the saved login session"
                ) from error
            if "ERR_HTTP_RESPONSE_CODE_FAILURE" in str(error):
                raise RuntimeError(
                    "X rejected the page request. Check the post in normal Chrome, "
                    "then retry without --headless to see whether X asks you to log in. "
                    "If it does, refresh the local cookies."
                ) from error
            raise
        if self._session_expected and not self._session_cookies_present():
            raise SessionRejectedError(
                "X did not retain the saved login session"
            )
        if response is not None and response.status >= 400:
            raise RuntimeError(
                f"X returned HTTP {response.status} for the post. "
                "Check the link and login session in normal Chrome."
            )

    def _session_cookies_present(self) -> bool:
        names = {cookie["name"] for cookie in self.context.cookies("https://x.com")}
        return {"auth_token", "ct0"}.issubset(names)

    def close(self) -> None:
        self.context.close()
        self.playwright.stop()
