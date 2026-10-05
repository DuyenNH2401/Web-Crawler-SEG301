"""Điều phối việc duyệt box, từng chủ đề và từng trang bình luận."""

from pathlib import Path
import time

from .config import FORUM_URL
from .database import save_comments, write_csv
from .models import Thread
from .network import create_session, get_page
from .parser import comments_on_page, next_page, threads_on_page


def crawl(forum_pages: int, max_threads: int, thread_pages: int, delay: float,
          db_path: Path, csv_path: Path) -> int:
    """Thu thập các bình luận rồi lưu vào SQLite và CSV."""
    all_threads: list[Thread] = []
    seen_threads: set[str] = set()
    seen_comments: set[str] = set()
    rows = []

    with create_session() as session:
        forum_url: str | None = FORUM_URL
        for _ in range(forum_pages):
            if not forum_url or len(all_threads) >= max_threads:
                break
            print(f"Đọc danh sách: {forum_url}")
            soup = get_page(session, forum_url)
            for thread in threads_on_page(soup):
                if thread.thread_id not in seen_threads:
                    all_threads.append(thread)
                    seen_threads.add(thread.thread_id)
                if len(all_threads) >= max_threads:
                    break
            forum_url = next_page(soup, forum_url)
            if forum_url and len(all_threads) < max_threads:
                time.sleep(delay)

        if not all_threads:
            raise RuntimeError("Không tìm thấy chủ đề công khai; hãy kiểm tra HTML hoặc quyền truy cập VOZ.")

        for thread in all_threads:
            page_url: str | None = thread.url
            print(f"Đọc chủ đề {thread.thread_id}: {thread.title}")
            for page_number in range(1, thread_pages + 1):
                if not page_url:
                    break
                time.sleep(delay)
                soup = get_page(session, page_url)
                comments = comments_on_page(soup, thread.thread_id, page_url,
                                            skip_original=page_number == 1)
                fresh = [comment for comment in comments if comment.comment_id not in seen_comments]
                save_comments(db_path, fresh)
                for comment in fresh:
                    seen_comments.add(comment.comment_id)
                    rows.append((thread, comment))
                print(f"  Trang {page_number}: {len(fresh)} bình luận")
                page_url = next_page(soup, page_url)

    write_csv(csv_path, rows)
    print(f"Đã lưu {len(rows)} bình luận vào {db_path} và {csv_path}")
    return len(rows)
