from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

import config


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
    normalized = urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        path,
        parsed.params,
        parsed.query,
        "",  
    ))
    return normalized


def extract_page_info(url, html, depth, status_code):
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.title
    title = title_tag.get_text(strip=True) if title_tag else ""

    text_content = soup.get_text(separator=" ", strip=True)

    domain = normalize_domain(urlparse(url).netloc)

    page_info = {
        "url": url,
        "domain": domain,
        "title": title,
        "content": text_content,
        "depth": depth,
        "status_code": status_code,
        "crawled_at": datetime.now(timezone.utc).isoformat(),
    }
    return page_info, soup


def is_valid_url(url):
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        return False

    path_lower = parsed.path.lower()
    for ext in config.IGNORED_EXTENSIONS:
        if path_lower.endswith(ext):
            return False

    return True


def is_allowed_domain(url):
    domain = normalize_domain(urlparse(url).netloc)
    allowed = {normalize_domain(d) for d in config.ALLOWED_DOMAINS}
    return domain in allowed


def extract_links(soup, current_url):
    candidates = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href:
            continue

        scheme_part = href.split(":", 1)[0].lower()
        if scheme_part in config.IGNORED_SCHEMES:
            continue

        absolute_url = urljoin(current_url, href)
        absolute_url = normalize_url(absolute_url)
        candidates.append(absolute_url)

    valid_links = []
    for link in candidates:
        if is_valid_url(link) and is_allowed_domain(link):
            valid_links.append(link)

    return valid_links
