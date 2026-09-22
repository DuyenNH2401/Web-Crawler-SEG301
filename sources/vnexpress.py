"""VnExpress adapter using the original parser and filtering rules."""

from urllib.parse import urlparse

import config
import parser

from models import Article
from sources.base import SourceAdapter


class VnExpressSource(SourceAdapter):
    name = "VnExpress"
    seed_urls = config.SEED_URLS
    allowed_domains = config.ALLOWED_DOMAINS
    headers = config.DEFAULT_HEADERS
    max_depth = config.MAX_DEPTH
    max_pages = config.MAX_PAGES
    request_timeout = config.REQUEST_TIMEOUT
    crawl_delay = config.CRAWL_DELAY
    ignored_extensions = config.IGNORED_EXTENSIONS
    ignored_schemes = config.IGNORED_SCHEMES
    ignored_paths = config.IGNORED_PATHS

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
        return parser.is_article_url(url)

    def parse_page_data(self, html_content: str, url: str, depth: int, status_code: int):
        return parser.parse_page_data(html_content, url, depth, status_code)

    def extract_links(self, html_content: str, current_url: str):
        return parser.extract_and_filter_links(
            html_content=html_content,
            current_url=current_url,
            allowed_domains=self.allowed_domains,
            ignored_extensions=self.ignored_extensions,
            ignored_schemes=self.ignored_schemes,
            ignored_paths=self.ignored_paths,
            articles_only=config.ARTICLES_ONLY,
        )
