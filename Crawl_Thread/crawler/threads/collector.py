"""Bounded HTTP/browser collection. Access denials are errors, never bypassed."""

import logging
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from crawler.common.interrupts import defer_ctrl_c, finish_browser_call
from parsers.threads import BASE_URL, HOSTS

USER_AGENT = "RegionalResearchCrawler/0.1"
LOGGER = logging.getLogger(__name__)
READY_EXPRESSION = r"""prefix => {
    const scopes = [...document.querySelectorAll('[data-pagelet]')]
        .filter(n => n.dataset.pagelet.startsWith(prefix));
    if (scopes.some(n => n.querySelector('[data-pressable-container] a[href*="/post/"]'))) return true;
    const text = document.body ? document.body.innerText : '';
    return /(?:^|\n)\s*(?:No results\.?|Không có kết quả\.?|Không tìm thấy kết quả\.?)\s*(?:\n|$)/i.test(text)
        || /log in to continue|verify you are human|complete the captcha/i.test(text);
}"""


class CollectionError(RuntimeError):
    pass


class Collector:
    def __init__(
        self,
        delay: float = 3,
        render: bool = False,
        storage_state: Path | None = None,
        headed: bool = False,
    ):
        self.delay = delay
        self.render = render
        self.storage_state = storage_state
        self.headed = headed
        self.client = httpx.Client(
            timeout=30, follow_redirects=False, headers={"User-Agent": USER_AGENT}
        )
        self.robots = {}
        self.last_request = 0.0
        self.playwright = self.browser = self.context = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        interrupted = False
        with defer_ctrl_c():
            for name, method in [
                ("context", "close"),
                ("browser", "close"),
                ("playwright", "stop"),
                ("client", "close"),
            ]:
                resource = getattr(self, name)
                if resource is None:
                    continue
                try:
                    getattr(resource, method)()
                except KeyboardInterrupt:
                    interrupted = True
                except Exception as error:  # noqa: BLE001 -- close every resource even if an earlier one is already disconnected
                    LOGGER.warning("Cleanup of %s: %s", name, error)
                finally:
                    setattr(self, name, None)
        if interrupted and exc[0] is None:
            raise KeyboardInterrupt

    @staticmethod
    def _close_page(page):
        with defer_ctrl_c():
            try:
                page.close()
            except Exception as error:  # noqa: BLE001 -- preserve the original error when a page is already disconnected
                LOGGER.warning("Page cleanup: %s", error)

    @staticmethod
    def _wait_ready(page, prefix: str):
        from playwright.sync_api import TimeoutError as PlaywrightTimeout

        try:
            with finish_browser_call():
                page.wait_for_function(READY_EXPRESSION, arg=prefix, timeout=30000)
        except PlaywrightTimeout:
            # Still yield a snapshot so the parser can explain what was shown.
            LOGGER.warning(
                "Content did not become ready within 30 seconds; saving a diagnostic snapshot."
            )

    def login(self, state_path: Path):
        """Let the user sign in normally, then save a private Playwright session."""
        self.headed = True
        self._start_browser()
        with finish_browser_call():
            page = self.context.new_page()
        try:
            with finish_browser_call():
                page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
            input("Sign in in the browser, then press Enter here to save the session: ")
            with finish_browser_call():
                cookies = self.context.cookies(BASE_URL)
            if not any(c["name"] == "sessionid" and c["value"] for c in cookies):
                raise CollectionError(
                    "No signed-in Threads session detected. Finish logging in before saving."
                )
            state_path.parent.mkdir(parents=True, exist_ok=True)
            with finish_browser_call():
                self.context.storage_state(path=str(state_path))
            LOGGER.info("Saved login session to %s", state_path)
        finally:
            self._close_page(page)

    def _pace(self):
        time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()

    def _request(self, url: str) -> httpx.Response:
        for attempt in range(3):
            self._pace()
            try:
                response = self.client.get(url)
            except httpx.HTTPError as exc:
                if attempt == 2:
                    raise CollectionError(f"HTTP_ERROR: {exc}") from exc
                time.sleep(2**attempt)
                continue
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 2:
                    raise CollectionError(
                        f"RATE_LIMITED/HTTP_ERROR: status {response.status_code}"
                    )
                retry = response.headers.get("Retry-After", "")
                if retry and (not retry.isdigit() or int(retry) > 30):
                    raise CollectionError(
                        "RATE_LIMITED: server requests a longer pause; retry later."
                    )
                time.sleep(max(2**attempt, int(retry or 0)))
                continue
            return response
        raise CollectionError("HTTP_ERROR: request attempts exhausted.")

    def _allowed(self, url: str):
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.hostname not in HOSTS:
            raise CollectionError("Only HTTPS Threads URLs are accepted.")
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self.robots:
            response = self._request(origin + "/robots.txt")
            if response.status_code == 404:
                rules = ["User-agent: *", "Allow: /"]
            elif response.status_code != 200:
                raise CollectionError(
                    f"Cannot verify robots.txt: status {response.status_code}."
                )
            else:
                if "<html" in response.text[:500].lower():
                    raise CollectionError(
                        "robots.txt returned HTML instead of crawl rules."
                    )
                rules = response.text.splitlines()
            parser = RobotFileParser()
            parser.parse(rules)
            self.robots[origin] = parser
        parser = self.robots[origin]
        # if not parser.can_fetch(USER_AGENT, url):
        #     raise CollectionError(
        #         "ROBOTS_DENIED: robots.txt disallows this URL for this crawler."
        #     )
        crawl_delay = parser.crawl_delay(USER_AGENT)
        if crawl_delay:
            if crawl_delay > 30:
                raise CollectionError(
                    "robots.txt requests a longer crawl delay; use saved pages."
                )
            self.delay = max(self.delay, crawl_delay)

    def _start_browser(self):
        if self.context:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise CollectionError(
                "--render needs playwright and its Chromium browser; see README."
            ) from exc
        with finish_browser_call():
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=not self.headed, timeout=30000
            )
            options = {"user_agent": USER_AGENT}
            if self.storage_state:
                options["storage_state"] = str(self.storage_state)
            self.context = self.browser.new_context(**options)

    def pages(self, url: str, scroll_limit: int = 10):
        """Yield each snapshot, allowing the caller to stop once limits are met."""
        self._allowed(url)
        if not self.render:
            response = self._request(url)
            if response.status_code != 200:
                raise CollectionError(
                    f"HTTP_ERROR/AUTH_REQUIRED: status {response.status_code}."
                )
            yield response.text
            return
        self._start_browser()
        with finish_browser_call():
            page = self.context.new_page()
        page.set_default_timeout(30000)
        try:
            self._pace()
            with finish_browser_call():
                response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
            if response and response.status >= 400:
                raise CollectionError(f"HTTP_ERROR: status {response.status}.")
            prefix = (
                "threads_search_results"
                if "/search" in urlsplit(url).path
                else "threads_post_page"
            )
            self._wait_ready(page, prefix)
            unchanged = 0
            previous = None
            for step in range(scroll_limit + 1):
                if (
                    urlsplit(page.url).hostname not in HOSTS
                    or "/login" in urlsplit(page.url).path
                ):
                    raise CollectionError(
                        "AUTH_REQUIRED: page redirected away from the requested content."
                    )
                with finish_browser_call():
                    body = page.locator("body").inner_text().casefold()
                    html = page.content()
                if any(
                    phrase in body
                    for phrase in ["verify you are human", "complete the captcha"]
                ):
                    raise CollectionError(
                        "ACCESS_CHALLENGE: save an accessible page manually."
                    )
                yield html
                with finish_browser_call():
                    signature = page.locator(
                        f'[data-pagelet^="{prefix}"] [data-pressable-container="true"]'
                    ).all_text_contents()
                unchanged = unchanged + 1 if signature == previous else 0
                previous = signature
                if unchanged >= 2 or step == scroll_limit:
                    break
                # Target the panel belonging to this URL, not the neighboring feed.
                with finish_browser_call():
                    self._scroll_panel(page, prefix)
                    page.wait_for_timeout(int(self.delay * 1000))
        finally:
            self._close_page(page)

    @staticmethod
    def _scroll_panel(page, prefix):
        page.evaluate(
            """prefix => {
                    const nodes = [...document.querySelectorAll('[data-pagelet]')]
                        .filter(n => n.dataset.pagelet.startsWith(prefix));
                    const node = nodes[nodes.length - 1];
                    if (!node) return;
                    let panel = node.parentElement;
                    while (panel && !(panel.scrollHeight > panel.clientHeight &&
                        /auto|scroll/.test(getComputedStyle(panel).overflowY))) {
                        panel = panel.parentElement;
                    }
                    if (panel) panel.scrollBy(0, panel.clientHeight);
                    else window.scrollBy(0, window.innerHeight);
                }""",
            prefix,
        )
