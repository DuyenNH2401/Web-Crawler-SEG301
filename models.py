"""Common records shared by all news-source crawlers."""

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class Article:
    source: str
    url: str
    title: str
    content: str
    depth: int
    status_code: int
    crawled_at: str
    summary: str = ""
    author: Optional[str] = None
    published_at: Optional[str] = None
    category: Optional[str] = None


@dataclass(frozen=True)
class Digest:
    topic: str
    articles: List[Article]
    content: str
    created_at: str
