"""Model Comment, chuẩn hóa dữ liệu và tên subreddit."""
from __future__ import annotations

from dataclasses import dataclass, replace
import math
import re
from typing import Any


def subreddit_name(value: str) -> str:
    value = value.removeprefix("r/").strip()
    if not re.fullmatch(r"[A-Za-z0-9_]{2,21}", value):
        raise ValueError("subreddit phải là tên, ví dụ python hoặc r/python")
    return value.lower()


@dataclass(frozen=True)
class Comment:
    id: str
    post_id: str | None = None
    parent_id: str | None = None
    subreddit: str | None = None
    body: str | None = None
    score: int | None = None
    created_utc: float | None = None
    edited_utc: float | None = None
    author_id: str | None = None
    author_name: str | None = None
    comment_url: str | None = None

    @classmethod
    def from_value(cls, value: Any, *, subreddit: str | None = None) -> Comment:
        if isinstance(value, cls):
            result = value
        elif isinstance(value, dict):
            if value.get("platform", "reddit") != "reddit":
                raise ValueError("platform phải là reddit")
            result = cls(id=value.get("comment_id", value.get("id")),
                         post_id=value.get("post_id"), parent_id=value.get("parent_id"),
                         subreddit=value.get("subreddit") or subreddit,
                         body=value.get("content", value.get("body")),
                         score=value.get("like_count", value.get("score")),
                         created_utc=value.get("created_at", value.get("created_utc")),
                         edited_utc=value.get("edited_utc"), author_id=value.get("author_id"),
                         author_name=value.get("author_name"), comment_url=value.get("comment_url"))
        else:
            author = getattr(value, "author", None)
            author_name = getattr(author, "name", None)
            # author_fullname is included in comment responses when available.
            # Never read author.id, which could issue an extra profile request.
            author_id = getattr(value, "author_fullname", None) if author is not None else None
            if isinstance(author_id, str):
                author_id = author_id.removeprefix("t2_")
            permalink = getattr(value, "permalink", None)
            if permalink and permalink.startswith("/"):
                permalink = "https://www.reddit.com" + permalink
            result = cls(id=getattr(value, "id", None), post_id=getattr(value, "link_id", None),
                         parent_id=getattr(value, "parent_id", None),
                         subreddit=getattr(getattr(value, "subreddit", None), "display_name", subreddit),
                         body=getattr(value, "body", None), score=getattr(value, "score", None),
                         created_utc=getattr(value, "created_utc", None),
                         author_id=author_id, author_name=author_name, comment_url=permalink)
        if not isinstance(result.id, str) or not re.fullmatch(r"[a-z0-9]+", result.id):
            raise ValueError("comment_id bắt buộc và phải là ID Reddit hợp lệ")
        if result.post_id is not None:
            if not isinstance(result.post_id, str) or not re.fullmatch(r"(?:t3_)?[a-z0-9]+", result.post_id):
                raise ValueError("invalid post ID")
            if not result.post_id.startswith("t3_"):
                result = replace(result, post_id="t3_" + result.post_id)
        if result.parent_id is not None and (not isinstance(result.parent_id, str)
                                            or not re.fullmatch(r"t[13]_[a-z0-9]+", result.parent_id)):
            raise ValueError("invalid parent ID")
        for field in (result.body, result.author_id, result.author_name, result.comment_url):
            if field is not None and not isinstance(field, str):
                raise ValueError("invalid text field")
        if result.score is not None and (not isinstance(result.score, int) or isinstance(result.score, bool)):
            raise ValueError("invalid like_count")
        for number in (result.created_utc, result.edited_utc):
            if number is not None and (isinstance(number, bool) or not isinstance(number, (int, float))
                                       or not math.isfinite(number) or number < 0):
                raise ValueError("invalid UTC timestamp")
        if result.subreddit is not None:
            subreddit_name(result.subreddit)
        return result
