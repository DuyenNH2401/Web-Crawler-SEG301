"""Các giá trị mặc định của crawler VOZ."""

from pathlib import Path

from shared_database import DEFAULT_DB


FORUM_URL = "https://voz.vn/f/chuyen-tro-linh-tinhtm.17/"
DEFAULT_CSV = Path(__file__).resolve().parent.parent / "data" / "voz_comments.csv"
DEFAULT_FORUM_PAGES = 1
DEFAULT_MAX_THREADS = 5
DEFAULT_THREAD_PAGES = 2
DEFAULT_DELAY = 1.5
REQUEST_TIMEOUT = 20
USER_AGENT = "Mozilla/5.0 (compatible; SEG301-VozCrawler/1.0)"

CSV_FIELDS = ("post_id", "thread_title", "comment_id", "author_name", "content",
              "created_at", "comment_url")
