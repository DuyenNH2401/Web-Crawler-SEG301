"""
Configuration settings for the Focused Web Crawler.
Topic: Health News (CNN Edition)
Course: SEG301 - Crawls and Feeds
"""
import os
import re

# ==========================================
# CRAWLER CONFIGURATION
# ==========================================
TOPIC = "Health News"

# Seed URLs to initiate the crawling process
SEED_URLS = [
    "https://edition.cnn.com/health"
]

# Allowed domains constraint to keep the crawl focused on CNN Edition
ALLOWED_DOMAINS = [
    "edition.cnn.com"
]

# Crawling constraints
MAX_DEPTH = 3           # Maximum crawl depth (Seed URL is depth 0)
MAX_PAGES = 100         # Maximum number of unique pages to download
REQUEST_TIMEOUT = 10    # HTTP request timeout in seconds
CRAWL_DELAY = 1.0       # Polite crawl delay between requests in seconds

# Chỉ cào bài báo health thực sự (phải khớp URL_PATTERN)
ARTICLES_ONLY = True

# URL Pattern: CNN Health article format
# Ví dụ: https://edition.cnn.com/2026/09/19/health/september-11-cancer-wave
URL_PATTERN = re.compile(
    r"^https://edition\.cnn\.com/\d{4}/\d{2}/\d{2}/health/[\w-]+$"
)

# CSS classes to exclude from content extraction
# Loại bỏ nội dung nằm trong các thẻ có class này
EXCLUDED_CSS_CLASSES = [
    "vossi-related-content_elevate__body"
]

# SQLite Database storage path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "crawler.db")

# HTTP Request Headers
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36 (SEG301EducationalBot/1.0)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
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
