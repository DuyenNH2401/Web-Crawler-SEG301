"""Nghiệp vụ thu thập, chống trùng, đồng bộ và nhập JSONL."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import DEFAULT_MAX_POSTS, DEFAULT_MORE_LIMIT, DELETED, LOG, SYNC_BATCH_SIZE
from .database import Store
from .models import Comment, subreddit_name
from .progress import CrawlProgress


def counters() -> dict[str, Any]:
    return dict(processed=0, saved=0, created=0, updated=0, deleted=0, skipped=0,
                duplicates=0, would_save=0, would_delete=0, limit_reached=False)


def consume(value: Any, store: Store, result: dict[str, Any], seen: set[str], *, dry_run: bool) -> None:
    c = Comment.from_value(value)
    result["processed"] += 1
    # Process deletion markers even if the same ID appeared earlier in this run.
    if c.body in DELETED:
        if dry_run:
            result["would_delete"] += 1
        else:
            result["deleted" if store.delete(c.id) else "skipped"] += 1
        return
    if c.id in seen:
        result["duplicates"] += 1
        return
    seen.add(c.id)
    if dry_run:
        result["would_save"] += 1
    else:
        result[store.save(c)] += 1
    result["saved"] += 1


def crawl(reddit: Any, store: Store, subreddit: str, *, max_comments: int,
          max_posts: int = DEFAULT_MAX_POSTS, more_limit: int = DEFAULT_MORE_LIMIT, dry_run: bool = False,
          progress: CrawlProgress | None = None) -> dict[str, Any]:
    if max_comments <= 0 or max_posts <= 0 or more_limit < 0:
        raise ValueError("invalid crawl limits")
    result = counters() | dict(posts=0, unexpanded_branches=0)
    seen: set[str] = set()
    posts = iter(reddit.subreddit(subreddit_name(subreddit)).new(limit=max_posts))
    while result["posts"] < max_posts and result["saved"] < max_comments:
        if progress is not None:
            progress.update(stage="Đang lấy danh sách bài")
        post = next(posts, None)
        if post is None:
            break
        post.comment_sort = "new"
        if progress is not None:
            progress.update(stage=f"Đang lấy comment bài {post.id}")
        remaining = post.comments.replace_more(limit=more_limit)
        result["posts"] += 1
        result["unexpanded_branches"] += len(remaining)
        if progress is not None:
            progress.update(posts=result["posts"], stage="Kiểm tra comment" if dry_run else "Lưu vào SQLite")
        for c in post.comments.list():
            saved_before = result["saved"]
            consume(Comment.from_value(c, subreddit=subreddit), store, result, seen, dry_run=dry_run)
            if progress is not None and result["saved"] != saved_before:
                progress.update(saved=result["saved"], report=True)
            if result["saved"] >= max_comments:
                break
        LOG.info("post=%s posts=%d saved=%d/%d unexpanded=%d", post.id, result["posts"],
                 result["saved"], max_comments, len(remaining))
    result["limit_reached"] = result["saved"] >= max_comments
    return result


def sync(reddit: Any, store: Store, *, dry_run: bool = False) -> dict[str, Any]:
    result = counters()
    ids = store.ids()
    seen: set[str] = set()
    for offset in range(0, len(ids), SYNC_BATCH_SIZE):
        batch = ids[offset:offset + SYNC_BATCH_SIZE]
        # Fully retrieve the batch before deleting IDs absent from the response.
        fetched = list(reddit.info(fullnames=[f"t1_{cid}" for cid in batch]))
        found = set()
        for c in fetched:
            consume(c, store, result, seen, dry_run=dry_run)
            found.add(c.id)
        for cid in set(batch) - found:
            if dry_run:
                result["would_delete"] += 1
            else:
                result["deleted"] += store.delete(cid)
        LOG.info("sync_batch=%d checked=%d deleted=%d", offset // SYNC_BATCH_SIZE + 1, len(batch), result["deleted"])
    return result


def import_jsonl(path: Path, store: Store, subreddit: str, *, max_comments: int,
                 dry_run: bool = False) -> dict[str, Any]:
    """Read our documented JSONL format; no assumptions about the RFR schema."""
    if max_comments <= 0:
        raise ValueError("max_comments phải > 0")
    subreddit = subreddit_name(subreddit)
    result = counters() | dict(filtered=0)
    seen: set[str] = set()
    with Path(path).open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
                if not isinstance(raw, dict):
                    raise ValueError
                c = Comment.from_value(raw, subreddit=subreddit)
            except (ValueError, TypeError, KeyError, AttributeError):
                raise ValueError(f"invalid JSONL record at line {line_number}; xem định dạng trong README") from None
            if c.subreddit.lower() != subreddit:
                result["filtered"] += 1
                continue
            consume(c, store, result, seen, dry_run=dry_run)
            if result["saved"] >= max_comments:
                break
    result["limit_reached"] = result["saved"] >= max_comments
    return result
