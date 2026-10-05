"""Parse rendered Threads HTML using selectors verified against sample_pages.

The URL shortcode is the record ID; numeric account IDs and exact reply parents
are not exposed by these snapshots. Never infer a parent from an @mention.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import unquote, urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from crawler.common.models import Comment, ParsedThread, Post
from crawler.common.normalize import normalize_text

BASE_URL = "https://www.threads.com"
HOSTS = {"threads.com", "www.threads.com", "threads.net", "www.threads.net"}
POST_PATH = re.compile(r"^/@([^/]+)/post/([A-Za-z0-9_-]+)(?:/media)?/?$")
BODY_SELECTOR = 'span[dir="auto"][style*="line-clamp"]'


class ParseError(ValueError):
    pass


@dataclass
class SearchPage:
    posts: list[Post]
    state: str
    login_limited: bool = False


def _login_limited(soup: BeautifulSoup) -> bool:
    text = normalize_text(soup.get_text(" ", strip=True)).casefold()
    return "log in for more threads about this topic" in text


def _no_results(soup: BeautifulSoup) -> bool:
    # Exact UI text, rather than a substring that could occur in a post.
    marker = soup.find(
        string=re.compile(
            r"^\s*(?:No results\.?|Không có kết quả\.?|Không tìm thấy kết quả\.?)\s*$",
            re.IGNORECASE,
        )
    )
    return marker is not None


def canonical_post_url(url: str) -> str | None:
    parts = urlsplit(urljoin(BASE_URL, url))
    match = POST_PATH.fullmatch(unquote(parts.path))
    if (
        parts.scheme not in {"https", "http"}
        or parts.hostname not in HOSTS
        or not match
    ):
        return None
    return f"{BASE_URL}/@{match[1]}/post/{match[2]}"


def snapshot_url(html: str) -> str | None:
    match = re.search(r"saved from url=\(\d+\)(https?://[^\s<>]+)", html[:1500])
    return match[1] if match else None


def parse_count(text: str) -> tuple[int | None, bool]:
    match = re.fullmatch(r"([\d,]+(?:\.\d+)?)\s*([KMB]?)", text.strip(), re.IGNORECASE)
    if not match:
        return None, False
    multiplier = {"": 1, "K": 1000, "M": 1000000, "B": 1000000000}[match[2].upper()]
    return int(float(match[1].replace(",", "")) * multiplier), bool(match[2])


def _content(card: Tag) -> str:
    chunks = []
    for outer in card.select(BODY_SELECTOR):
        if outer.find_parent("a") or outer.find_parent(attrs={"role": "button"}):
            continue
        if outer.select_one("time"):
            continue
        # Plain child spans contain authored text. Styled child spans contain
        # usernames, Replying to labels, counters and other UI in these files.
        for inner in outer.find_all("span", recursive=False):
            if inner.attrs:
                continue
            clone = BeautifulSoup(str(inner), "lxml")
            for control in clone.select('[role="button"], button, script, style'):
                control.decompose()
            for br in clone.select("br"):
                br.replace_with("\n")
            text = normalize_text(clone.get_text())
            if text:
                chunks.append(text)
    return "\n".join(chunks)


def _timestamp(card: Tag) -> str | None:
    node = card.select_one("time[datetime]")
    if node is None:
        return None
    try:
        timestamp = datetime.fromisoformat(node["datetime"].replace("Z", "+00:00"))
    except ValueError:
        return None
    if timestamp.tzinfo is None:
        return None
    return timestamp.astimezone(timezone.utc).isoformat()


def _likes(card: Tag) -> tuple[int | None, bool]:
    for button in card.select('[role="button"], button'):
        title = button.select_one("svg title")
        label = normalize_text(
            button.get("aria-label", "") or (title.get_text() if title else "")
        )
        if label.casefold() not in {"like", "unlike"}:
            continue
        visible = normalize_text(button.get_text(" ", strip=True))
        visible = re.sub(r"^(?:Like|Unlike)\s*", "", visible, flags=re.IGNORECASE)
        return parse_count(visible)
    return None, False


def _permalink(card: Tag) -> str | None:
    for link in card.select("a[href]"):
        if link.select_one("time"):
            url = canonical_post_url(link["href"])
            if url:
                return url
    for link in card.select("a[href]"):
        url = canonical_post_url(link["href"])
        if url:
            return url
    return None


def _cards(scope: Tag | BeautifulSoup) -> list[Tag]:
    # Ignore wrappers around another pressable card to prevent quoted/nested
    # content from being merged into the outer record.
    return [
        c
        for c in scope.select('[data-pressable-container="true"]')
        if not c.select_one('[data-pressable-container="true"]')
    ]


def _record(card: Tag, source: str) -> Post | None:
    url = _permalink(card)
    if not url:
        return None
    match = POST_PATH.fullmatch(urlsplit(url).path)
    count, approximate = _likes(card)
    return Post(
        post_id=match[2],
        post_url=url,
        content=_content(card),
        author_name=match[1],
        created_at=_timestamp(card),
        source_html=source,
        like_count=count,
        like_count_is_approximate=approximate,
        text_may_be_truncated=True
        if card.select_one('[style*="-webkit-line-clamp"], [style*="max-lines"]')
        else None,
    )


class ThreadsParser:
    def discover(self, html: str) -> list[Post]:
        """Return unique search candidates, excluding the neighboring feed."""
        return self.parse_search(html).posts

    def parse_search(self, html: str) -> SearchPage:
        """Distinguish actual empty searches from loading, login and DOM failures."""
        soup = BeautifulSoup(html, "lxml")
        scopes = soup.select('[data-pagelet^="threads_search_results"]')
        found = {}
        for scope in scopes:
            for card in _cards(scope):
                record = _record(card, "")
                if record and record.post_id not in found:
                    found[record.post_id] = record
        limited = _login_limited(soup)
        if found:
            return SearchPage(list(found.values()), "results", limited)
        if _no_results(soup):
            return SearchPage([], "empty", limited)
        if not scopes:
            text = normalize_text(soup.get_text(" ", strip=True)).casefold()
            if "log in or sign up for threads" in text or "log in to continue" in text:
                raise ParseError(
                    "AUTH_REQUIRED: no search results are visible; sign in using main.py login."
                )
            raise ParseError(
                "No Threads search-results section; results may still be loading or the DOM changed."
            )
        raise ParseError(
            "Search sections contain no post cards or empty-results marker; page may still be loading."
        )

    def parse(
        self, html: str, post_url: str | None = None, source: str = ""
    ) -> ParsedThread:
        soup = BeautifulSoup(html, "lxml")
        origin = post_url or snapshot_url(html)
        if not origin:
            for selector, attribute in [
                ("meta[property='og:url']", "content"),
                ("link[rel='canonical']", "href"),
            ]:
                node = soup.select_one(selector)
                if node and canonical_post_url(node.get(attribute, "")):
                    origin = node[attribute]
                    break
        target = canonical_post_url(origin or "")
        if not target:
            raise ParseError(
                "Missing post URL; pass --post-url. The homepage canonical is insufficient."
            )
        scopes = soup.select('[data-pagelet^="threads_post_page"]')
        if not scopes:
            raise ParseError(
                "No rendered Threads post section; HTTP may require --render or a saved page."
            )
        records = []
        seen = set()
        for scope in scopes:
            for card in _cards(scope):
                record = _record(card, source)
                if record and record.post_id not in seen:
                    seen.add(record.post_id)
                    records.append((card, record))
        root = next((p for _, p in records if p.post_url == target), None)
        if root is None:
            raise ParseError("Requested post is absent from rendered post cards.")
        warnings = [
            "Only loaded cards are collected; total comment coverage is unknown.",
            "Numeric author IDs, exact reply parents and text completeness are unavailable.",
        ]
        comments = []
        root_index = next(
            i for i, (_, record) in enumerate(records) if record.post_id == root.post_id
        )
        for card, record in records[root_index + 1 :]:
            if record.post_id == root.post_id:
                continue
            if not record.content:
                warnings.append(
                    f"Skipped non-text/unsupported comment {record.post_id}."
                )
                continue
            # Preserve the visible conversation group without asserting that
            # every later card replies directly to the first card in the group.
            group = card.find_parent(attrs={"data-virtualized": True})
            head = _permalink(_cards(group)[0]) if group and _cards(group) else None
            group_id = head.rsplit("/", 1)[-1] if head else "UNKNOWN"
            comments.append(
                Comment(
                    comment_id=record.post_id,
                    comment_url=record.post_url,
                    post_id=root.post_id,
                    content=record.content,
                    author_name=record.author_name,
                    created_at=record.created_at,
                    source_html=source,
                    reply_group_id=group_id,
                    like_count=record.like_count,
                    like_count_is_approximate=record.like_count_is_approximate,
                    text_may_be_truncated=record.text_may_be_truncated,
                )
            )
        return ParsedThread(root, comments, warnings)
