"""Logic điều phối cào bài viết và comment."""
from __future__ import annotations

import sys
from typing import Any

from .database import DELETED, Store


def crawl(reddit: Any, store: Store, subreddit: str, *, max_comments: int,
          max_posts: int = 100, dry_run: bool = False, progress: Any = None) -> dict[str, Any]:
    """Cào comment từ các bài mới trong subreddit đến khi đạt giới hạn."""
    sub = subreddit.lower().removeprefix("r/")
    result = dict(processed=0, saved=0, created=0, updated=0, deleted=0, skipped=0,
                  duplicates=0, would_save=0, would_delete=0, posts=0, unexpanded_branches=0)
    seen: set[str] = set()
    for pid in reddit.new_posts(sub, limit=max_posts):
        if result["saved"] >= max_comments or result["posts"] >= max_posts:
            break
        comments, unexpanded = reddit.comments(sub, pid)
        result["posts"] += 1
        result["unexpanded_branches"] += unexpanded
        for c in comments:
            cid = c.get("id") or c.get("comment_id")
            result["processed"] += 1
            if c.get("body") in DELETED or c.get("content") in DELETED:
                if dry_run:
                    result["would_delete"] += 1
                else:
                    action = store.save(c)
                    result[action] += 1
                continue
            if cid in seen:
                result["duplicates"] += 1
                continue
            seen.add(cid)
            if dry_run:
                result["would_save"] += 1
            else:
                action = store.save(c)
                result[action] += 1
            result["saved"] += 1
            print(f"[{result['saved']}/{max_comments}] Đã lưu comment {cid} (bài {pid})", file=sys.stderr)
            if result["saved"] >= max_comments:
                break
    result["limit_reached"] = result["saved"] >= max_comments
    return result
