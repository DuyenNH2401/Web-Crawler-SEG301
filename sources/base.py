"""Small adapter contract used by the shared crawler engine."""

from typing import Dict, List, Set


class SourceAdapter:
    name = ""
    seed_urls: List[str] = []
    allowed_domains: List[str] = []
    headers: Dict[str, str] = {}
    max_depth = 3
    max_pages = 100
    request_timeout = 10
    crawl_delay = 1.0
    ignored_extensions: Set[str] = set()
    ignored_schemes: Set[str] = set()
    ignored_paths: Set[str] = set()

    def prepare_html(self, html_content: str) -> str:
        return html_content

    def is_allowed_url(self, url: str) -> bool:
        raise NotImplementedError

    def is_article_candidate(self, url: str, depth: int, html_content: str) -> bool:
        return depth > 0

    def parse_page_data(self, html_content: str, url: str, depth: int, status_code: int):
        raise NotImplementedError

    def extract_links(self, html_content: str, current_url: str) -> List[str]:
        raise NotImplementedError
