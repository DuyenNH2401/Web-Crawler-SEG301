"""CNN adapter preserving the original CNN Health URL rule."""

import re
from typing import List
from urllib.parse import urlparse

from bs4 import BeautifulSoup

import config
import parser

from sources.base import SourceAdapter


SEED_URLS = ["https://edition.cnn.com/health"]
ALLOWED_DOMAINS = ["edition.cnn.com"]
MAX_DEPTH = 3
MAX_PAGES = 100
REQUEST_TIMEOUT = 10
CRAWL_DELAY = 1.0
URL_PATTERN = re.compile(
    r"^https://edition\.cnn\.com/\d{4}/\d{2}/\d{2}/health/[\w-]+$"
)
EXCLUDED_CSS_CLASSES = ["vossi-related-content_elevate__body"]


def is_cnn_health_article(url: str) -> bool:
    return bool(URL_PATTERN.match(url.rstrip("/")))


def remove_excluded_elements(html_content: str, excluded_classes: List[str]) -> str:
    if not excluded_classes:
        return html_content

    soup = BeautifulSoup(html_content, "html.parser")
    for css_class in excluded_classes:
        for element in soup.find_all(class_=re.compile(re.escape(css_class))):
            element.decompose()
    return str(soup)


class CNNSource(SourceAdapter):
    name = "CNN"
    seed_urls = SEED_URLS
    allowed_domains = ALLOWED_DOMAINS
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36 (SEG301EducationalBot/1.0)"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
    }
    max_depth = MAX_DEPTH
    max_pages = MAX_PAGES
    request_timeout = REQUEST_TIMEOUT
    crawl_delay = CRAWL_DELAY
    ignored_extensions = config.IGNORED_EXTENSIONS
    ignored_schemes = config.IGNORED_SCHEMES
    ignored_paths = config.IGNORED_PATHS

    def prepare_html(self, html_content: str) -> str:
        return remove_excluded_elements(html_content, EXCLUDED_CSS_CLASSES)

    def is_allowed_url(self, url: str) -> bool:
        parsed = urlparse(url)
        path = parsed.path.lower()
        return (
            parsed.scheme.lower() in ("http", "https")
            and parser.is_domain_allowed(parsed.netloc, self.allowed_domains)
            and not any(path.endswith(ext) for ext in self.ignored_extensions)
            and not any(
                path == ignored or path.startswith(ignored)
                for ignored in self.ignored_paths
            )
        )

    def is_article_candidate(self, url: str, depth: int, html_content: str) -> bool:
        return is_cnn_health_article(url)

    def parse_page_data(self, html_content: str, url: str, depth: int, status_code: int):
        return parser.parse_page_data(html_content, url, depth, status_code)

    def extract_links(self, html_content: str, current_url: str):
        # The original CNN branch temporarily replaced parser.is_article_url.
        # Filtering after the original generic rules preserves the same result
        # without changing shared parser state.
        candidates = parser.extract_and_filter_links(
            html_content=html_content,
            current_url=current_url,
            allowed_domains=self.allowed_domains,
            ignored_extensions=self.ignored_extensions,
            ignored_schemes=self.ignored_schemes,
            ignored_paths=self.ignored_paths,
            articles_only=False,
        )
        return [url for url in candidates if is_cnn_health_article(url)]
