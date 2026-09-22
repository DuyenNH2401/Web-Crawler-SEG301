"""
parser.py - Tasks 4, 5 and 7: page parsing, link extraction, URL filtering
and URL normalization.
"""

from datetime import datetime
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

import config

# Tags whose text is navigation / boilerplate rather than article content.
NOISE_TAGS = ("script", "style", "noscript", "nav", "header", "footer", "aside", "form")


# --------------------------------------------------------------------------
# Task 7 - URL normalization
# --------------------------------------------------------------------------
def normalize_url(url):
    """
    Return a canonical form of `url` so that URLs which point at the same page
    are recognised as duplicates.

    Applied rules:
      - lowercase the scheme and host (paths stay case-sensitive)
      - drop the #fragment
      - drop a default port (:80 / :443)
      - drop a trailing slash, except on the site root
    """
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


# --------------------------------------------------------------------------
# Task 5 - URL filtering
# --------------------------------------------------------------------------
def is_allowed_domain(url):
    """True when the host is an allowed domain or a subdomain of one."""
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    for domain in config.ALLOWED_DOMAINS:
        if host == domain or host.endswith("." + domain):
            return True
    return False


def is_blocked_subdomain(url):
    """
    True for on-domain hosts that carry no journalism - the shop, the account
    portals, the jobs board. Checked as a whole label so that a hypothetical
    `supportive.theguardian.com` is not caught by the `support` entry.
    """
    host = urlparse(url).netloc.lower()
    label = host.split(".", 1)[0]
    return label in config.BLOCKED_SUBDOMAINS


def is_crawlable(url):
    """
    Decide whether `url` should ever be fetched.

    Returns (True, "") when it should, or (False, reason) when it should not.
    The reason string is what the crawler prints and counts in its statistics.
    """
    lowered = url.lower()

    for scheme in config.BLOCKED_SCHEMES:
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
    for ext in config.BLOCKED_EXTENSIONS:
        if path.endswith(ext):
            return False, "non-web resource"

    for prefix in config.BLOCKED_PATH_PREFIXES:
        if path.startswith(prefix):
            return False, "blocked path"

    return True, ""


def extract_links(soup, current_url):
    """
    Task 5 - collect every <a href> on the page, turn it into an absolute,
    normalized URL, and split the result into accepted and rejected URLs.

    Returns (valid_urls, all_urls, rejected) where `rejected` is a list of
    (url, reason) pairs used for the statistics.
    """
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


# --------------------------------------------------------------------------
# Task 4 - page information
# --------------------------------------------------------------------------
def make_soup(html):
    return BeautifulSoup(html, "html.parser")


def extract_page_data(soup, url, depth, status_code):
    """Build the structured page record that Task 4 asks for."""
    title = soup.title.get_text(strip=True) if soup.title else ""

    # Remove boilerplate before taking the text, so the stored content is
    # closer to the actual article.
    for tag in soup.find_all(NOISE_TAGS):
        tag.decompose()

    content = soup.get_text(separator=" ", strip=True)
    if config.MAX_CONTENT_CHARS:
        content = content[:config.MAX_CONTENT_CHARS]

    return {
        "url": url,
        "domain": urlparse(url).netloc.lower(),
        "title": title,
        "content": content,
        "depth": depth,
        "status_code": status_code,
        "crawled_at": datetime.now().isoformat(timespec="seconds"),
    }
