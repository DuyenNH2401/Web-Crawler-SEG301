"""CNN adapter preserving the original CNN Health URL rule."""

import re
from typing import List
from urllib.parse import urlparse

from bs4 import BeautifulSoup

import config
import parser

from sources.base import SourceAdapter


URL_PATTERN = re.compile(
    r"^https://edition\.cnn\.com/\d{4}/\d{2}/\d{2}/health/[\w/-]+(?:\.html)?$"
)
EXCLUDED_CSS_CLASSES = ["vossi-related-content_elevate__body"]


def is_cnn_health_article(url: str) -> bool:
    return bool(URL_PATTERN.match(url.rstrip("/")))


def is_cnn_health_section(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc.lower() == "edition.cnn.com" and parsed.path.lower().startswith("/health")


def remove_excluded_elements(html_content: str, excluded_classes: List[str]) -> str:
    if not excluded_classes:
        return html_content

    soup = BeautifulSoup(html_content, "html.parser")
    for css_class in excluded_classes:
        for element in soup.find_all(class_=re.compile(re.escape(css_class))):
            element.decompose()
    return str(soup)


class CNNSource(SourceAdapter):
    settings = config.SOURCE_CONFIGS["cnn"]
    name = settings["name"]
    seed_urls = settings["seed_urls"]
    allowed_domains = settings["allowed_domains"]
    headers = settings["headers"]
    max_depth = settings["max_depth"]
    max_pages = settings["max_pages"]
    request_timeout = settings["request_timeout"]
    crawl_delay = settings["crawl_delay"]
    ignored_extensions = settings["ignored_extensions"]
    ignored_schemes = settings["ignored_schemes"]
    ignored_paths = settings["ignored_paths"]

    def prepare_html(self, html_content: str) -> str:
        return remove_excluded_elements(html_content, EXCLUDED_CSS_CLASSES)

    def is_allowed_url(self, url: str) -> bool:
        parsed = urlparse(url)
        path = parsed.path.lower()
        if not (
            parsed.scheme.lower() in ("http", "https")
            and parser.is_domain_allowed(parsed.netloc, self.allowed_domains)
            and not any(path.endswith(ext) for ext in self.ignored_extensions)
            and not any(
                path == ignored or path.startswith(ignored)
                for ignored in self.ignored_paths
            )
        ):
            return False
        return is_cnn_health_article(url) or is_cnn_health_section(url)

    def is_article_candidate(self, url: str, depth: int, html_content: str) -> bool:
        return is_cnn_health_article(url)

    def parse_page_data(self, html_content: str, url: str, depth: int, status_code: int):
        return parser.parse_page_data(html_content, url, depth, status_code)

    def extract_links(self, html_content: str, current_url: str):
        candidates = parser.extract_and_filter_links(
            html_content=html_content,
            current_url=current_url,
            allowed_domains=self.allowed_domains,
            ignored_extensions=self.ignored_extensions,
            ignored_schemes=self.ignored_schemes,
            ignored_paths=self.ignored_paths,
            articles_only=False,
        )
        return [url for url in candidates if is_cnn_health_article(url) or is_cnn_health_section(url)]
