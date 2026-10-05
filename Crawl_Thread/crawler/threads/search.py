from urllib.parse import parse_qs, urlencode, urlsplit

from crawler.common.normalize import matched_keywords
from parsers.threads import BASE_URL, HOSTS, ThreadsParser


def search_url(keyword: str) -> str:
    return f"{BASE_URL}/search?{urlencode({'q': keyword, 'serp_type': 'default'})}"


def canonical_search_url(url: str, keyword_only: bool = False) -> str | None:
    parts = urlsplit(url)
    keyword = parse_qs(parts.query).get("q", [""])[0].strip()
    if (
        parts.scheme != "https"
        or parts.hostname not in HOSTS
        or parts.path.rstrip("/") != "/search"
        or not keyword
    ):
        return None
    return keyword if keyword_only else search_url(keyword)


def discover_urls(html: str, keywords: list[str] | None = None) -> list[str]:
    candidates = ThreadsParser().discover(html)
    return [
        p.post_url
        for p in candidates
        if keywords is None or matched_keywords(p.content, keywords)
    ]
