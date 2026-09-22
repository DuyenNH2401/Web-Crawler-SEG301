"""Global Times adapter preserving the original branch rules."""

from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from sources.base import SourceAdapter


SEED_URLS = ["https://www.globaltimes.cn/"]
ALLOWED_DOMAINS = ["globaltimes.cn"]
IGNORED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".css", ".js", ".zip", ".pdf", ".mp3", ".mp4", ".wav",
    ".woff", ".woff2", ".ttf", ".eot", ".xml", ".json",
}
IGNORED_SCHEMES = {"mailto", "javascript", "tel", "ftp"}


def normalize_domain(netloc):
    netloc = netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def normalize_url(url):
    parsed = urlparse(url)
    path = parsed.path
    if path.endswith("/") and path != "/":
        path = path.rstrip("/")
    return urlunparse((
        parsed.scheme.lower(), parsed.netloc.lower(), path,
        parsed.params, parsed.query, "",
    ))


def extract_page_info(url, html, depth, status_code):
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.title
    title = title_tag.get_text(strip=True) if title_tag else ""
    text_content = soup.get_text(separator=" ", strip=True)
    return {
        "url": url,
        "domain": normalize_domain(urlparse(url).netloc),
        "title": title,
        "content": text_content,
        "depth": depth,
        "status_code": status_code,
        "crawled_at": datetime.now(timezone.utc).isoformat(),
    }, soup


def is_valid_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    path_lower = parsed.path.lower()
    return not any(path_lower.endswith(ext) for ext in IGNORED_EXTENSIONS)


def is_allowed_domain(url):
    return normalize_domain(urlparse(url).netloc) in {
        normalize_domain(domain) for domain in ALLOWED_DOMAINS
    }


def extract_links(soup, current_url):
    candidates = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href:
            continue
        scheme_part = href.split(":", 1)[0].lower()
        if scheme_part in IGNORED_SCHEMES:
            continue
        candidates.append(normalize_url(urljoin(current_url, href)))

    return [
        link for link in candidates
        if is_valid_url(link) and is_allowed_domain(link)
    ]


class GlobalTimesSource(SourceAdapter):
    name = "Global Times"
    seed_urls = SEED_URLS
    allowed_domains = ALLOWED_DOMAINS
    headers = {
        "User-Agent": "SEG301-EducationalCrawler/1.0 (student project; contact: hovinhhung29@gmail.com)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
    max_depth = 3
    max_pages = 100
    request_timeout = 20
    crawl_delay = 1.5

    def is_allowed_url(self, url: str) -> bool:
        return is_valid_url(url) and is_allowed_domain(url)

    def parse_page_data(self, html_content: str, url: str, depth: int, status_code: int):
        return extract_page_info(url, html_content, depth, status_code)[0]

    def extract_links(self, html_content: str, current_url: str):
        return extract_links(BeautifulSoup(html_content, "html.parser"), current_url)
