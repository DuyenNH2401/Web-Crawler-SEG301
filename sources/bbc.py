"""BBC adapter copied from the original BBC parser rules."""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from sources.base import SourceAdapter


BBC_DOMAINS = ("bbc.com", "bbc.co.uk")
BBC_ARTICLE_PATH_PATTERNS = (
    re.compile(r"^/(?:[a-z0-9-]+/)*articles/[a-z0-9]{8,20}/?$"),
    re.compile(r"^/news/(?:[a-z0-9-]+/)*[a-z0-9-]+-\d{5,}(?:\.html)?/?$"),
)
BBC_EXCLUDED_PATH_PREFIXES = (
    "/news/av", "/news/in_pictures", "/news/videos", "/video", "/videos",
    "/reel", "/audio", "/sounds", "/iplayer", "/programmes", "/newsletters",
    "/search", "/ugc", "/userinfo", "/rss", "/feeds",
)
ARTICLE_JUNK_SELECTORS = (
    "script", "style", "noscript", "svg", "iframe", "figure", "figcaption",
    "picture", "video", "audio", "aside", '[role="complementary"]',
    '[data-component="ad-slot"]', '[data-component="advertisement-block"]',
    '[data-component="byline-block"]', '[data-component="tag-list-block"]',
    '[data-component="video-block"]', '[data-component="audio-block"]',
    '[data-testid="ad-slot"]', '[data-testid="ad-unit"]',
    '[data-testid^="dotcom-"]', '[data-testid="tagsAndSocialStyled"]',
    '[data-testid="socialShareTriggerButton"]', '[class*="AdSlot"]',
    '[class*="Caption"]', '[id*="smp-ads"]',
)
IGNORED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".css", ".js", ".json", ".xml", ".zip", ".tar", ".gz", ".rar", ".7z",
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv",
    ".exe", ".dmg", ".apk", ".bin",
}
IGNORED_SCHEMES = {"mailto", "javascript", "tel", "data", "sms", "ftp"}
IGNORED_PATHS = {"/error.html", "/error"}


def is_domain_allowed(netloc: str, allowed_domains: List[str]) -> bool:
    hostname = netloc.split("@")[-1].split(":")[0].lower().rstrip(".")
    for domain in allowed_domains:
        domain = domain.lower().rstrip(".")
        if hostname == domain or hostname.endswith("." + domain):
            return True
    return False


def _has_path_prefix(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def is_excluded_bbc_url(url: str) -> bool:
    path = urlparse(url).path.lower().rstrip("/") or "/"
    return any(_has_path_prefix(path, prefix) for prefix in BBC_EXCLUDED_PATH_PREFIXES)


def is_crawlable_bbc_url(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme.lower() in ("http", "https")
        and is_domain_allowed(parsed.netloc, list(BBC_DOMAINS))
        and not is_excluded_bbc_url(url)
    )


def is_article_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https"):
        return False
    if not is_domain_allowed(parsed.netloc, list(BBC_DOMAINS)):
        return False
    if is_excluded_bbc_url(url):
        return False
    path = parsed.path.lower()
    return any(pattern.fullmatch(path) for pattern in BBC_ARTICLE_PATH_PATTERNS)


def _clean_text(element) -> str:
    return element.get_text(" ", strip=True) if element else ""


def _extract_title(soup: BeautifulSoup, article_page: bool) -> str:
    if article_page:
        headline = soup.select_one('[data-component="headline-block"] h1') or soup.find("h1")
        title = _clean_text(headline)
        if title:
            return title
    if soup.title:
        title = _clean_text(soup.title)
        if title:
            return title
    social_title = soup.find("meta", property="og:title")
    if social_title and social_title.get("content"):
        return social_title["content"].strip()
    headline = soup.find("h1")
    return _clean_text(headline) or "Untitled Page"


def _is_article_page(soup: BeautifulSoup, url: str) -> bool:
    if is_article_url(url):
        return True
    return bool(
        soup.select_one('[data-component="headline-block"]')
        and soup.select_one('[data-component="layout-block"]')
    )


def _extract_article_content(soup: BeautifulSoup) -> str:
    article = soup.find("article")
    if article is None:
        return ""
    for selector in ARTICLE_JUNK_SELECTORS:
        for element in article.select(selector):
            element.decompose()
    body_containers = article.select('[data-component="layout-block"]') or [article]
    paragraphs: List[str] = []
    seen: Set[str] = set()
    for container in body_containers:
        for paragraph in container.find_all("p"):
            text = _clean_text(paragraph)
            if len(text) < 10 or text in seen:
                continue
            seen.add(text)
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _extract_topic_content(soup: BeautifulSoup, page_url: str) -> str:
    cards: List[str] = []
    seen: Set[str] = set()

    def add_card(headline, description=None) -> None:
        anchor = headline.find_parent("a", href=True)
        if anchor is None:
            return
        target_url = urljoin(page_url, anchor["href"].strip())
        if not is_crawlable_bbc_url(target_url):
            return
        headline_text = _clean_text(headline)
        if not headline_text or headline_text in seen:
            return
        seen.add(headline_text)
        description_text = _clean_text(description)
        cards.append(
            f"{headline_text}\n{description_text}"
            if description_text and description_text != headline_text
            else headline_text
        )

    for headline in soup.select('[data-testid="card-headline"]'):
        card = headline.find_parent("article")
        description = card.select_one('[data-testid="card-description"]') if card else None
        add_card(headline, description)

    for promo in soup.select('[data-testid="promo"]'):
        headline = promo.select_one('[class*="PromoHeadline"]')
        if headline is None:
            continue
        description = promo.select_one('p[class*="Paragraph"]')
        add_card(headline, description)

    if cards:
        return "\n\n".join(cards)

    for selector in ARTICLE_JUNK_SELECTORS + ("header", "footer", "nav"):
        for element in soup.select(selector):
            element.decompose()
    main = soup.find("main") or soup.body or soup
    return _clean_text(main)


def parse_page_data(html_content: str, url: str, depth: int, status_code: int) -> Dict[str, Any]:
    soup = BeautifulSoup(html_content, "html.parser")
    article_page = _is_article_page(soup, url)
    title = _extract_title(soup, article_page)
    content = _extract_article_content(soup) if article_page else _extract_topic_content(soup, url)
    return {
        "url": url,
        "domain": urlparse(url).netloc.lower(),
        "title": title,
        "content": content,
        "depth": depth,
        "status_code": status_code,
        "crawled_at": datetime.now().isoformat(),
    }


def _canonicalize_link(url: str, article: bool = False) -> str:
    parsed = urlparse(url)
    if article:
        parsed = parsed._replace(query="")
    parsed = parsed._replace(
        scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower(), fragment=""
    )
    return urlunparse(parsed)


def extract_and_filter_links(html_content: str, current_url: str) -> List[str]:
    soup = BeautifulSoup(html_content, "html.parser")
    seen_in_page: Set[str] = set()
    valid_links: List[str] = []
    link_scope = soup.find("main") or soup

    for tag in link_scope.find_all("a", href=True):
        href = tag["href"].strip()
        if not href:
            continue
        absolute_url = urljoin(current_url, href)
        parsed = urlparse(absolute_url)
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https") or scheme in IGNORED_SCHEMES:
            continue
        if not is_domain_allowed(parsed.netloc, list(BBC_DOMAINS)):
            continue
        path_lower = parsed.path.lower()
        if any(path_lower.endswith(ext) for ext in IGNORED_EXTENSIONS):
            continue
        if any(path_lower == path or path_lower.startswith(path) for path in IGNORED_PATHS):
            continue
        if is_excluded_bbc_url(absolute_url):
            continue
        article = is_article_url(absolute_url)
        clean_url = _canonicalize_link(absolute_url, article=article)
        if clean_url in seen_in_page:
            continue
        seen_in_page.add(clean_url)
        valid_links.append(clean_url)
    return valid_links


class BBCSource(SourceAdapter):
    name = "BBC"
    seed_urls = ["https://www.bbc.co.uk/business"]
    allowed_domains = list(BBC_DOMAINS)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36 (SEG301EducationalBot/1.0)"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
    }
    max_depth = 3
    max_pages = 100
    request_timeout = 10
    crawl_delay = 1.0

    def is_allowed_url(self, url: str) -> bool:
        return is_crawlable_bbc_url(url)

    def is_article_candidate(self, url: str, depth: int, html_content: str) -> bool:
        return is_article_url(url)

    def parse_page_data(self, html_content: str, url: str, depth: int, status_code: int):
        return parse_page_data(html_content, url, depth, status_code)

    def extract_links(self, html_content: str, current_url: str):
        return extract_and_filter_links(html_content, current_url)
