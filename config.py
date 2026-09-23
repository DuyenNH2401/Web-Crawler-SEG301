"""
Configuration settings for the Focused Web Crawler.
Topic: News & Information (five news sources)
Course: SEG301 - Crawls and Feeds
"""
import os

# ==========================================
# CRAWLER CONFIGURATION
# ==========================================
TOPIC = "News & Information"

# Seed URLs for each source.
SEED_URLS = {
    "vnexpress": ["https://e.vnexpress.net/"],
    "cnn": ["https://edition.cnn.com/health"],
    # www.bbc.com does not resolve on some networks; the UK News endpoint serves
    # the same crawlable BBC article URLs and is already in the domain allowlist.
    "bbc": ["https://www.bbc.co.uk/news"],
    "guardian": [
        "https://www.theguardian.com",
        #"https://www.theguardian.com/world",
    ],
    "globaltimes": ["https://www.globaltimes.cn/"],
}

# Allowed domains for each source.
ALLOWED_DOMAINS = {
    "vnexpress": ["e.vnexpress.net"],
    "cnn": ["edition.cnn.com"],
    "bbc": ["bbc.com", "bbc.co.uk"],
    "guardian": ["theguardian.com"],
    "globaltimes": ["globaltimes.cn"],
}

# Crawling constraints
MAX_DEPTH = 3           # Maximum crawl depth (Seed URL is depth 0)
MAX_PAGES = 100         # Maximum number of unique pages to download
REQUEST_TIMEOUT = 10    # HTTP request timeout in seconds
CRAWL_DELAY = 1.0       # Polite crawl delay between requests in seconds

ARTICLES_ONLY = True

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

# Runtime settings for every source. Parser and URL rules stay in sources/.
SOURCE_CONFIGS = {
    "vnexpress": {
        "name": "VnExpress",
        "seed_urls": SEED_URLS["vnexpress"],
        "allowed_domains": ALLOWED_DOMAINS["vnexpress"],
        "headers": DEFAULT_HEADERS,
        "max_depth": MAX_DEPTH,
        "max_pages": MAX_PAGES,
        "request_timeout": REQUEST_TIMEOUT,
        "crawl_delay": CRAWL_DELAY,
        "ignored_extensions": IGNORED_EXTENSIONS,
        "ignored_schemes": IGNORED_SCHEMES,
        "ignored_paths": IGNORED_PATHS,
        "articles_only": ARTICLES_ONLY,
    },
    "cnn": {
        "name": "CNN",
        "seed_urls": SEED_URLS["cnn"],
        "allowed_domains": ALLOWED_DOMAINS["cnn"],
        "headers": DEFAULT_HEADERS,
        "max_depth": 3,
        "max_pages": 100,
        "request_timeout": 10,
        "crawl_delay": 1.0,
        "ignored_extensions": IGNORED_EXTENSIONS,
        "ignored_schemes": IGNORED_SCHEMES,
        "ignored_paths": IGNORED_PATHS,
    },
    "bbc": {
        "name": "BBC",
        # Use the directly crawlable News section instead of the unreliable
        # www.bbc.com hostname.
        "seed_urls": SEED_URLS["bbc"],
        "allowed_domains": ALLOWED_DOMAINS["bbc"],
        "headers": DEFAULT_HEADERS,
        "max_depth": 3,
        "max_pages": 100,
        "request_timeout": 10,
        "crawl_delay": 1.0,
        "ignored_extensions": IGNORED_EXTENSIONS,
        "ignored_schemes": IGNORED_SCHEMES,
        "ignored_paths": IGNORED_PATHS,
    },
    "guardian": {
        "name": "The Guardian",
        "seed_urls": SEED_URLS["guardian"],
        "allowed_domains": ALLOWED_DOMAINS["guardian"],
        "headers": {
            "User-Agent": "SEG301-StudentCrawler/1.0 (coursework; contact: student@fpt.edu.vn)"
        },
        "max_depth": 2,
        "max_pages": 100,
        "request_timeout": 10,
        "crawl_delay": 1.0,
        "max_content_chars": 20000,
    },
    "globaltimes": {
        "name": "Global Times",
        "seed_urls": SEED_URLS["globaltimes"],
        "allowed_domains": ALLOWED_DOMAINS["globaltimes"],
        "headers": {
            "User-Agent": "SEG301-EducationalCrawler/1.0 (student project; contact: hovinhhung29@gmail.com)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        },
        "max_depth": 3,
        "max_pages": 100,
        "request_timeout": 20,
        "crawl_delay": 1.5,
        "ignored_extensions": {
            ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
            ".css", ".js", ".zip", ".pdf", ".mp3", ".mp4", ".wav",
            ".woff", ".woff2", ".ttf", ".eot", ".xml", ".json",
        },
        "ignored_schemes": {"mailto", "javascript", "tel", "ftp"},
    },
}
