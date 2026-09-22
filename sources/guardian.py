"""The Guardian adapter preserving the original branch rules."""

from datetime import datetime
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

import config
from sources.base import SourceAdapter


GUARDIAN_SETTINGS = config.SOURCE_CONFIGS["guardian"]
ALLOWED_DOMAINS = GUARDIAN_SETTINGS["allowed_domains"]
BLOCKED_SUBDOMAINS = (
    "holidays", "support", "manage", "profile", "jobs", "patrons",
    "advertising", "usadvertising", "ausadvertising", "syndication",
    "workforus", "sourcing", "contribute", "membership",
)
BLOCKED_SCHEMES = ("mailto:", "javascript:", "tel:", "sms:", "ftp:", "file:")
BLOCKED_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico", ".bmp",
    ".css", ".js", ".json", ".xml", ".rss", ".zip", ".gz", ".tar", ".rar",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".mp3", ".mp4", ".avi", ".mov", ".wav", ".webm",
)
BLOCKED_PATH_PREFIXES = (
    "/video", "/audio", "/pictures", "/ng-interactive", "/crosswords", "/puzzles",
    "/signin", "/register", "/profile", "/account", "/help", "/info", "/about",
    "/contactus", "/membership", "/subscribe", "/contribute", "/give", "/jobs",
    "/guardian-masterclasses", "/guardian-live-events", "/index", "/tone", "/applications",
)
MAX_CONTENT_CHARS = GUARDIAN_SETTINGS["max_content_chars"]


def normalize_url(url):
    url, _ = urldefrag(url.strip())
    parts = urlparse(url)
    host = parts.netloc.lower()
    if host.endswith(":80"):
        host = host[:-3]
    elif host.endswith(":443"):
        host = host[:-4]
    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse((parts.scheme.lower(), host, path, parts.params, parts.query, ""))


def is_allowed_domain(url):
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return any(host == domain or host.endswith("." + domain) for domain in ALLOWED_DOMAINS)


def is_blocked_subdomain(url):
    label = urlparse(url).netloc.lower().split(".", 1)[0]
    return label in BLOCKED_SUBDOMAINS


def is_crawlable(url):
    lowered = url.lower()
    for scheme in BLOCKED_SCHEMES:
        if lowered.startswith(scheme):
            return False, "non-http scheme"
    parts = urlparse(url)
    if parts.scheme not in ("http", "https"):
        return False, "non-http scheme"
    if not parts.netloc:
        return False, "no host"
    if not is_allowed_domain(url):
        return False, "outside allowed domains"
    if is_blocked_subdomain(url):
        return False, "non-editorial subdomain"
    path = parts.path.lower()
    if any(path.endswith(ext) for ext in BLOCKED_EXTENSIONS):
        return False, "non-web resource"
    if any(path.startswith(prefix) for prefix in BLOCKED_PATH_PREFIXES):
        return False, "blocked path"
    return True, ""


def extract_links(soup, current_url):
    valid, all_urls, rejected = [], [], []
    seen = set()
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href:
            continue
        absolute_url = normalize_url(urljoin(current_url, href))
        if absolute_url in seen:
            continue
        seen.add(absolute_url)
        all_urls.append(absolute_url)
        ok, reason = is_crawlable(absolute_url)
        if ok:
            valid.append(absolute_url)
        else:
            rejected.append((absolute_url, reason))
    return valid, all_urls, rejected


def make_soup(html):
    return BeautifulSoup(html, "html.parser")


def extract_page_data(soup, url, depth, status_code):
    title = soup.title.get_text(strip=True) if soup.title else ""
    for tag in soup.find_all(("script", "style", "noscript", "nav", "header", "footer", "aside", "form")):
        tag.decompose()
    content = soup.get_text(separator=" ", strip=True)
    if MAX_CONTENT_CHARS:
        content = content[:MAX_CONTENT_CHARS]
    return {
        "url": url,
        "domain": urlparse(url).netloc.lower(),
        "title": title,
        "content": content,
        "depth": depth,
        "status_code": status_code,
        "crawled_at": datetime.now().isoformat(timespec="seconds"),
    }


class GuardianSource(SourceAdapter):
    name = GUARDIAN_SETTINGS["name"]
    seed_urls = GUARDIAN_SETTINGS["seed_urls"]
    allowed_domains = GUARDIAN_SETTINGS["allowed_domains"]
    headers = GUARDIAN_SETTINGS["headers"]
    max_depth = GUARDIAN_SETTINGS["max_depth"]
    max_pages = GUARDIAN_SETTINGS["max_pages"]
    request_timeout = GUARDIAN_SETTINGS["request_timeout"]
    crawl_delay = GUARDIAN_SETTINGS["crawl_delay"]

    def is_allowed_url(self, url: str) -> bool:
        return is_crawlable(url)[0]

    def is_article_candidate(self, url: str, depth: int, html_content: str) -> bool:
        return depth > 0

    def parse_page_data(self, html_content: str, url: str, depth: int, status_code: int):
        return extract_page_data(make_soup(html_content), url, depth, status_code)

    def extract_links(self, html_content: str, current_url: str):
        return extract_links(make_soup(html_content), current_url)[0]
