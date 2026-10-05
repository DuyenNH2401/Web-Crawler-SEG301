"""Đọc danh sách chủ đề và các bình luận từ HTML của VOZ."""

from datetime import datetime, timezone
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from models import Comment

from .config import FORUM_URL
from .models import Thread


THREAD_ID = re.compile(r"\.(\d+)/?$")
POST_ID = re.compile(r"^post-(\d+)$")


def next_page(soup: BeautifulSoup, current_url: str) -> str | None:
    """Tìm nút 'Sau' của thanh phân trang."""
    link = soup.select_one("a.pageNav-jump--next[href]")
    return urljoin(current_url, link["href"]) if link else None


def threads_on_page(soup: BeautifulSoup) -> list[Thread]:
    """Lấy ID, tiêu đề và URL của các chủ đề trên trang box."""
    threads = []
    for item in soup.select(".structItem--thread"):
        link = item.select_one(".structItem-title a[data-tp-primary][href]")
        if not link:
            continue
        url = urljoin(FORUM_URL, link["href"])
        if urlparse(url).netloc != "voz.vn":
            continue
        match = THREAD_ID.search(urlparse(url).path)
        if match:
            threads.append(Thread(match.group(1), link.get_text(" ", strip=True), url))
    return threads


def comments_on_page(soup: BeautifulSoup, thread_id: str, page_url: str,
                     skip_original: bool) -> list[Comment]:
    """Lấy bài trả lời, bỏ bài gốc ở trang đầu."""
    posts = soup.select("article.message--post[data-content]")
    if not posts:
        raise RuntimeError(f"Không tìm thấy bài đăng tại {page_url}; cấu trúc trang có thể đã đổi.")

    comments = []
    for index, post in enumerate(posts):
        if skip_original and index == 0:
            continue
        match = POST_ID.match(post.get("data-content", ""))
        body = post.select_one(".message-body .bbWrapper")
        if not match or not body:
            continue
        # Trích dẫn là lời của người khác, không phải nội dung mới.
        for quote in body.select(".bbCodeBlock--quote, blockquote, script, style"):
            quote.decompose()
        content = body.get_text(" ", strip=True)
        if not content:
            continue

        user = post.select_one(".message-name a")
        clock = post.select_one(".message-attribution-main time[datetime]")
        author_name = user.get_text(" ", strip=True) if user else post.get("data-author", "UNKNOWN")
        author_id = user.get("data-user-id", "UNKNOWN") if user else "UNKNOWN"
        created_at = ""
        if clock:
            created_at = datetime.fromisoformat(clock["datetime"]).astimezone(timezone.utc).isoformat()

        comments.append(Comment(
            platform="voz", comment_id=match.group(1), content=content,
            author_id=author_id, author_name=author_name or "UNKNOWN",
            parent_id="UNKNOWN", post_id=thread_id,
            comment_url=f"{page_url}#post-{match.group(1)}",
            created_at=created_at, like_count=0,
            collected_at=datetime.now(timezone.utc).isoformat(),
        ))
    return comments
