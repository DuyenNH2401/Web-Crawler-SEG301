"""Giá trị mặc định dùng chung; không chứa cookie hoặc credentials."""
import logging
from pathlib import Path

LOG = logging.getLogger("reddit_crawler")
DELETED = {"[deleted]", "[removed]"}

DEFAULT_DB = Path("data/reddit.sqlite3")
DEFAULT_RETENTION_HOURS = 48
DEFAULT_MAX_POSTS = 100
DEFAULT_MORE_LIMIT = 8
DEFAULT_REQUEST_DELAY = 2
DEFAULT_TIMEOUT = 30
DEFAULT_SHOW_LIMIT = 10
DEFAULT_PROGRESS_INTERVAL = 5
PUBLIC_USER_AGENT = "linux:seg301-public-comments:v0.1.0"
SESSION_USER_AGENT = "linux:seg301-session-comments:v0.1.0"

MAX_RESPONSE_BYTES = 10 * 1024 * 1024
MAX_COMMENTS_PER_RESPONSE = 500
MAX_POSTS_PER_PAGE = 100
SYNC_BATCH_SIZE = 100
MAX_COOKIE_HEADER_CHARS = 65536
MAX_HTTP_ATTEMPTS = 3
