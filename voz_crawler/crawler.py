"""Lấy chủ đề và bình luận VOZ bằng requests + Beautiful Soup."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
import re
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from database import upsert_comments
from models import Comment
from shared_database import DEFAULT_DB


FORUM_URL = "https://voz.vn/f/chuyen-tro-linh-tinhtm.17/"
DEFAULT_CSV = Path(__file__).resolve().parent.parent / "data" / "voz_comments.csv"
THREAD_ID = re.compile(r"\.(\d+)/?$")
POST_ID = re.compile(r"^post-(\d+)$")
CSV_FIELDS = ("post_id", "thread_title", "comment_id", "author_name", "content",
              "created_at", "comment_url")


def get_page(session: requests.Session, url: str) -> BeautifulSoup:
    """Tải một trang HTML; báo lỗi rõ ràng nếu truy cập thất bại."""
    response = session.get(url, timeout=20)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def next_page(soup: BeautifulSoup, current_url: str) -> str | None:
    """Lấy liên kết 'Sau' trên thanh phân trang XenForo."""
    link = soup.select_one("a.pageNav-jump--next[href]")
    return urljoin(current_url, link["href"]) if link else None


def threads_on_page(soup: BeautifulSoup) -> list[tuple[str, str, str]]:
    """Trả về (ID, tiêu đề, URL) của các chủ đề trong box F17."""
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
            threads.append((match.group(1), link.get_text(" ", strip=True), url))
    return threads


def comments_on_page(soup: BeautifulSoup, thread_id: str, page_url: str,
                     skip_original: bool) -> list[Comment]:
    """Đọc các bài trả lời; bỏ bài gốc ở trang đầu."""
    comments = []
    posts = soup.select("article.message--post[data-content]")
    if not posts:
        raise RuntimeError(f"Không tìm thấy bài đăng tại {page_url}; cấu trúc trang có thể đã đổi.")
    for index, post in enumerate(posts):
        if skip_original and index == 0:
            continue
        match = POST_ID.match(post.get("data-content", ""))
        body = post.select_one(".message-body .bbWrapper")
        if not match or not body:
            continue
        # Lời trích dẫn không phải nội dung mới của bình luận này.
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


def crawl(forum_pages: int, max_threads: int, thread_pages: int, delay: float,
          db_path: Path, csv_path: Path) -> int:
    """Duyệt box, từng chủ đề, rồi lưu bình luận vào SQLite và CSV."""
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; SEG301-VozCrawler/1.0)"})
    all_threads: list[tuple[str, str, str]] = []
    seen_threads: set[str] = set()
    forum_url: str | None = FORUM_URL

    for _ in range(forum_pages):
        if not forum_url or len(all_threads) >= max_threads:
            break
        print(f"Đọc danh sách: {forum_url}")
        soup = get_page(session, forum_url)
        for thread in threads_on_page(soup):
            if thread[0] not in seen_threads:
                all_threads.append(thread)
                seen_threads.add(thread[0])
            if len(all_threads) >= max_threads:
                break
        forum_url = next_page(soup, forum_url)
        if forum_url and len(all_threads) < max_threads:
            time.sleep(delay)

    if not all_threads:
        raise RuntimeError("Không tìm thấy chủ đề công khai; hãy kiểm tra HTML hoặc quyền truy cập VOZ.")

    rows: list[dict[str, str]] = []
    seen_comments: set[str] = set()
    for thread_id, title, first_url in all_threads:
        page_url: str | None = first_url
        print(f"Đọc chủ đề {thread_id}: {title}")
        for page_number in range(1, thread_pages + 1):
            if not page_url:
                break
            time.sleep(delay)
            soup = get_page(session, page_url)
            comments = comments_on_page(soup, thread_id, page_url, skip_original=page_number == 1)
            fresh = [comment for comment in comments if comment.comment_id not in seen_comments]
            upsert_comments(str(db_path), fresh)
            for comment in fresh:
                seen_comments.add(comment.comment_id)
                rows.append({
                    "post_id": thread_id, "thread_title": title,
                    "comment_id": comment.comment_id, "author_name": comment.author_name,
                    "content": comment.content, "created_at": comment.created_at,
                    "comment_url": comment.comment_url,
                })
            print(f"  Trang {page_number}: {len(fresh)} bình luận")
            page_url = next_page(soup, page_url)

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Đã lưu {len(rows)} bình luận vào {db_path} và {csv_path}")
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cào bình luận công khai trong box Chuyện trò linh tinh của VOZ")
    parser.add_argument("--forum-pages", type=int, default=1, help="Số trang danh sách chủ đề (mặc định: 1)")
    parser.add_argument("--max-threads", type=int, default=5, help="Số chủ đề tối đa (mặc định: 5)")
    parser.add_argument("--thread-pages", type=int, default=2, help="Số trang mỗi chủ đề (mặc định: 2)")
    parser.add_argument("--delay", type=float, default=1.5, help="Nghỉ giữa các yêu cầu, giây (mặc định: 1.5)")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="File SQLite chung")
    parser.add_argument("--output", type=Path, default=DEFAULT_CSV, help="File CSV xuất ra")
    args = parser.parse_args(argv)
    if args.forum_pages < 1 or args.max_threads < 1 or args.thread_pages < 1 or args.delay < 0:
        parser.error("Số trang và số chủ đề phải >= 1; delay phải >= 0")
    try:
        crawl(args.forum_pages, args.max_threads, args.thread_pages,
              args.delay, args.db, args.output)
    except (requests.RequestException, RuntimeError) as error:
        parser.exit(1, f"Không thể cào VOZ: {error}\n")
    return 0
