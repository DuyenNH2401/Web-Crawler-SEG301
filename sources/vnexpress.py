"""VnExpress adapter using the original parser and filtering rules."""

from urllib.parse import urlparse

import config
import parser

from models import Article
from sources.base import SourceAdapter


class VnExpressSource(SourceAdapter):
    settings = config.SOURCE_CONFIGS["vnexpress"]
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
            articles_only=self.settings["articles_only"],
        )
