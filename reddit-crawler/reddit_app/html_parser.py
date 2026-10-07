"""Parse và chuẩn hóa dữ liệu bài viết và comment cào từ HTML Reddit."""
from __future__ import annotations

import re
from typing import Any
from bs4 import BeautifulSoup

from .parser import normalize_comment


def clean_text_from_html(tag: Any) -> str:
    """Trích xuất text sạch từ tag HTML (xử lý cả TemplateString của Web Components)."""
    if not tag:
        return ""
    paragraphs = [re.sub(r"<[^>]+>", "", str(p)).strip() for p in tag.find_all("p")]
    if paragraphs:
        return "\n".join(p for p in paragraphs if p)
    return re.sub(r"<[^>]+>", " ", str(tag)).strip()


def parse_posts_html(html: str) -> list[dict[str, Any]]:
    """Trích xuất danh sách bài viết từ HTML của subreddit (thẻ <shreddit-post>)."""
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    posts: list[dict[str, Any]] = []
    for p in soup.find_all("shreddit-post"):
        raw_id = p.get("id") or ""
        pid = raw_id.removeprefix("t3_")
        permalink = p.get("permalink") or ""
        author = p.get("author") or ""
        title_el = p.find("a", slot="title") or p.find("div", slot="title")
        title = title_el.get_text(strip=True) if title_el else ""
        try:
            cnt = int(p.get("comment-count") or 0)
        except (ValueError, TypeError):
            cnt = 0

        posts.append({
            "id": pid,
            "post_id": f"t3_{pid}" if pid else "",
            "permalink": permalink,
            "author": author,
            "title": title,
            "comment_count": cnt,
        })
    return posts


def parse_comments_html(html: str, subreddit: str = "") -> tuple[list[dict[str, Any]], int]:
    """Trích xuất và chuẩn hóa danh sách comment từ HTML bài viết (thẻ <shreddit-comment>)."""
    if not html:
        return [], 0
    soup = BeautifulSoup(html, "html.parser")
    comments: list[dict[str, Any]] = []
    sub = subreddit.lower().removeprefix("r/")

    for c in soup.find_all("shreddit-comment"):
        raw_cid = c.get("thingid") or ""
        cid = raw_cid.removeprefix("t1_")
        author = c.get("author")
        
        score_val = None
        score_raw = c.get("score")
        if score_raw is not None:
            try:
                score_val = int(score_raw)
            except (ValueError, TypeError):
                score_val = None

        post_id = c.get("postid") or ""
        permalink = c.get("permalink") or ""

        # Lấy nội dung comment
        content_el = soup.find("div", id=f"{raw_cid}-post-rtjson-content") or c.find("div", slot="comment")
        content = clean_text_from_html(content_el)

        raw_comment = {
            "id": cid,
            "comment_id": cid,
            "body": content,
            "content": content,
            "author": author,
            "author_name": author,
            "parent_id": None,
            "post_id": post_id,
            "link_id": post_id,
            "permalink": permalink,
            "comment_url": permalink,
            "score": score_val,
            "like_count": score_val,
            "subreddit": sub,
            "created_at": None,
        }
        comments.append(normalize_comment(raw_comment, subreddit=sub))

    return comments, 0
