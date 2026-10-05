"""Parse và chuẩn hóa dữ liệu JSON bài viết và comment từ Reddit."""
from __future__ import annotations

from typing import Any

DELETED = {"[deleted]", "[removed]"}


def parse_posts(data: Any) -> list[str]:
    """Trích xuất danh sách post_id từ JSON listing bài viết mới."""
    if not isinstance(data, dict):
        return []
    children = data.get("data", {}).get("children", [])
    return [c["data"]["id"] for c in children if c.get("kind") == "t3" and isinstance(c.get("data"), dict)]


def parse_comments(data: Any, subreddit: str) -> tuple[list[dict[str, Any]], int]:
    """Duyệt cây comment và replies từ JSON bài viết, trả về danh sách comment chuẩn hoá và số nhánh chưa mở."""
    if not isinstance(data, list) or len(data) < 2:
        return [], 0
    comments, unexpanded = [], 0
    queue = list(data[1].get("data", {}).get("children", []))
    sub = subreddit.lower().removeprefix("r/")

    while queue:
        item = queue.pop(0)
        kind = item.get("kind")
        if kind == "more":
            unexpanded += 1
        elif kind == "t1":
            raw = item.get("data", {})
            comments.append(normalize_comment(raw, subreddit=sub))
            replies = raw.get("replies")
            if isinstance(replies, dict):
                queue.extend(replies.get("data", {}).get("children", []))

    return comments, unexpanded


def normalize_comment(raw: dict[str, Any], *, subreddit: str | None = None) -> dict[str, Any]:
    """Chuẩn hoá dữ liệu thô từ Reddit thành schema comment 11 cột, giữ alias tương thích."""
    cid = raw.get("comment_id") or raw.get("id")
    body = raw.get("content") or raw.get("body")
    sub = (raw.get("subreddit") or subreddit or "").lower().removeprefix("r/") or None

    author = raw.get("author")
    author_name = raw.get("author_name") or (author if author not in DELETED else None)
    author_id = raw.get("author_id") or (raw.get("author_fullname", "").removeprefix("t2_") if author_name else None) or None

    post_id = raw.get("post_id") or raw.get("link_id")
    if post_id and not str(post_id).startswith("t3_"):
        post_id = f"t3_{post_id}"

    url = raw.get("comment_url") or raw.get("permalink")
    if url and str(url).startswith("/"):
        url = f"https://www.reddit.com{url}"

    score = raw.get("like_count") if raw.get("like_count") is not None else raw.get("score")
    created = raw.get("created_at") if raw.get("created_at") is not None else raw.get("created_utc")

    return {
        "platform": "reddit",
        "id": cid,
        "comment_id": cid,
        "body": body,
        "content": body,
        "author_id": author_id,
        "author_name": author_name,
        "parent_id": raw.get("parent_id"),
        "post_id": post_id,
        "link_id": post_id,
        "comment_url": url,
        "permalink": url,
        "created_at": created,
        "created_utc": created,
        "score": score,
        "like_count": score,
        "subreddit": sub,
    }
