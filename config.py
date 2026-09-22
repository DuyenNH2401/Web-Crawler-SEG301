"""
Configuration settings for the Focused Web Crawler.
Topic: News & Information (VnExpress International)
Course: SEG301 - Crawls and Feeds
"""
import os

# ==========================================
# CRAWLER CONFIGURATION
# ==========================================
TOPIC = "News & Information"

# Seed URLs to initiate the crawling process
SEED_URLS = [
    "https://e.vnexpress.net/"
]

# Allowed domains constraint to keep the crawl focused on VnExpress International
ALLOWED_DOMAINS = [
    "e.vnexpress.net"
]

# Crawling constraints
MAX_DEPTH = 3           # Maximum crawl depth (Seed URL is depth 0)
MAX_PAGES = 100         # Maximum number of unique pages to download
REQUEST_TIMEOUT = 10    # HTTP request timeout in seconds
CRAWL_DELAY = 1.0       # Polite crawl delay between requests in seconds

# Chỉ cào bài báo thực sự (bắt buộc đuôi .html và có mã bài viết)
# Loại bỏ các trang danh mục như /news/life/wellness, /news/news...
ARTICLES_ONLY = True

# SQLite Database storage path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "crawler.db")
DIGEST_PATH = os.path.join(DATA_DIR, "digest.md")

# HTTP Request Headers
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36 (SEG301EducationalBot/1.0)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
}

# Filtering rules: non-web resources and unneeded file extensions
IGNORED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".css", ".js", ".json", ".xml",
    ".zip", ".tar", ".gz", ".rar", ".7z",
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv",
    ".exe", ".dmg", ".apk", ".bin"
}

# Filtering rules: ignored URL schemes
IGNORED_SCHEMES = {"mailto", "javascript", "tel", "data", "sms", "ftp"}

# Filtering rules: paths to ignore (e.g. error redirect pages)
IGNORED_PATHS = {"/error.html", "/error"}
