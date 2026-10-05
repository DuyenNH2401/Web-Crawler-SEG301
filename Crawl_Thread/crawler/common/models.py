from dataclasses import dataclass, field
from datetime import datetime, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Post:
    post_id: str
    post_url: str
    content: str
    author_name: str
    created_at: str | None
    source_html: str = ""
    platform: str = "threads"
    author_id: str = "UNKNOWN"
    like_count: int | None = None
    like_count_is_approximate: bool = False
    text_may_be_truncated: bool | None = None
    collected_at: str = field(default_factory=utc_now)


@dataclass
class Comment:
    comment_id: str
    comment_url: str
    post_id: str
    content: str
    author_name: str
    created_at: str | None
    source_html: str = ""
    platform: str = "threads"
    author_id: str = "UNKNOWN"
    parent_id: str = "UNKNOWN"
    reply_group_id: str = "UNKNOWN"
    parent_source: str = "unavailable"
    like_count: int | None = None
    like_count_is_approximate: bool = False
    text_may_be_truncated: bool | None = None
    collected_at: str = field(default_factory=utc_now)


@dataclass
class ParsedThread:
    post: Post
    comments: list[Comment]
    warnings: list[str] = field(default_factory=list)
