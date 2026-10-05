"""Package reddit_app: crawler Reddit tinh gọn chỉ dùng thư viện chuẩn."""
from .client import RedditClient
from .crawler import crawl
from .database import Store, database_stats, show_comments
from .main import main
from .parser import normalize_comment, parse_comments, parse_posts

__all__ = [
    "RedditClient",
    "Store",
    "crawl",
    "database_stats",
    "show_comments",
    "main",
    "parse_posts",
    "parse_comments",
    "normalize_comment",
]
