"""Global Times adapter preserving the original branch rules."""

from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

import config
from sources.base import SourceAdapter


GLOBAL_TIMES_SETTINGS = config.SOURCE_CONFIGS["globaltimes"]
ALLOWED_DOMAINS = GLOBAL_TIMES_SETTINGS["allowed_domains"]
IGNORED_EXTENSIONS = GLOBAL_TIMES_SETTINGS["ignored_extensions"]
IGNORED_SCHEMES = GLOBAL_TIMES_SETTINGS["ignored_schemes"]


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
    name = GLOBAL_TIMES_SETTINGS["name"]
    seed_urls = GLOBAL_TIMES_SETTINGS["seed_urls"]
    allowed_domains = GLOBAL_TIMES_SETTINGS["allowed_domains"]
    headers = GLOBAL_TIMES_SETTINGS["headers"]
    max_depth = GLOBAL_TIMES_SETTINGS["max_depth"]
    max_pages = GLOBAL_TIMES_SETTINGS["max_pages"]
    request_timeout = GLOBAL_TIMES_SETTINGS["request_timeout"]
    crawl_delay = GLOBAL_TIMES_SETTINGS["crawl_delay"]

    def is_allowed_url(self, url: str) -> bool:
        return is_valid_url(url) and is_allowed_domain(url)

    def parse_page_data(self, html_content: str, url: str, depth: int, status_code: int):
        return extract_page_info(url, html_content, depth, status_code)[0]

    def extract_links(self, html_content: str, current_url: str):
        return extract_links(BeautifulSoup(html_content, "html.parser"), current_url)
