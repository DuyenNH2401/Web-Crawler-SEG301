"""Package reddit_app: crawler Reddit hỗ trợ cả endpoint JSON và BeautifulSoup HTML."""
from .client import RedditClient
from .crawler import crawl
from .database import Store, database_stats, show_comments
from .html_parser import parse_comments_html, parse_posts_html
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
    "parse_posts_html",
    "parse_comments_html",
    "normalize_comment",
]
