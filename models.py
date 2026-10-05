"""Shared record used to store comments from all social platforms."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Comment:
    """One reply with UTC timestamps in ISO 8601 format."""

    platform: str
    comment_id: str
    content: str
    author_id: str
    author_name: str
    parent_id: str
    post_id: str
    comment_url: str
    created_at: str
    like_count: int
    collected_at: str
