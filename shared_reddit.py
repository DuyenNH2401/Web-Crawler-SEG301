"""Adapter between the Reddit crawler and the shared comments database."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import math
import sqlite3
import time

import database
from models import Comment as SharedComment


def utc_text(timestamp: float | None) -> str:
    if timestamp is None:
        return "1970-01-01T00:00:00Z"
    return datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class SharedRedditStore:
    """Expose the Reddit Store interface over the unified schema."""

    def __init__(self, path: Path | str):
        self.path = str(path)
        self.conn = database.get_connection(self.path)
        database.ensure_comments_schema(self.conn)
        self.ensure_schema()

    def ensure_schema(self) -> None:
        with self.conn:
            self.conn.execute("""CREATE TABLE IF NOT EXISTS comment_metadata (
                platform TEXT NOT NULL, comment_id TEXT NOT NULL, subreddit TEXT,
                PRIMARY KEY(platform, comment_id),
                FOREIGN KEY(platform, comment_id) REFERENCES comments(platform, comment_id)
                    ON DELETE CASCADE)""")
            self.conn.execute("CREATE INDEX IF NOT EXISTS metadata_subreddit ON comment_metadata(subreddit)")
        self.conn.execute("PRAGMA foreign_keys = ON")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self) -> None:
        self.conn.close()

    def ids(self) -> list[str]:
        return [row[0] for row in self.conn.execute(
            "SELECT comment_id FROM comments WHERE platform='reddit' ORDER BY comment_id")]

    def delete(self, cid: str) -> int:
        with self.conn:
            return self.conn.execute(
                "DELETE FROM comments WHERE platform='reddit' AND comment_id=?", (cid,)).rowcount

    def save(self, value, *, now: float | None = None) -> str:
        from reddit_app.config import DELETED
        from reddit_app.models import Comment

        c = Comment.from_value(value)
        if c.body in DELETED:
            return "deleted" if self.delete(c.id) else "skipped"
        exists = self.conn.execute(
            "SELECT 1 FROM comments WHERE platform='reddit' AND comment_id=?", (c.id,)).fetchone()
        record = SharedComment(
            platform="reddit", comment_id=c.id, content=c.body or "",
            author_id=c.author_id or "UNKNOWN", author_name=c.author_name or "UNKNOWN",
            parent_id=c.parent_id or "UNKNOWN", post_id=c.post_id or "UNKNOWN",
            comment_url=c.comment_url or "", created_at=utc_text(c.created_utc),
            like_count=max(0, c.score or 0), collected_at=utc_text(now or time.time()),
        )
        with self.conn:
            self.conn.execute("""INSERT INTO comments
                (platform, comment_id, content, author_id, author_name, parent_id,
                 post_id, comment_url, created_at, like_count, collected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(platform, comment_id) DO UPDATE SET
                    content=excluded.content, author_id=excluded.author_id,
                    author_name=excluded.author_name, parent_id=excluded.parent_id,
                    post_id=excluded.post_id, comment_url=excluded.comment_url,
                    created_at=excluded.created_at, like_count=excluded.like_count,
                    collected_at=excluded.collected_at""",
                (record.platform, record.comment_id, record.content, record.author_id,
                 record.author_name, record.parent_id, record.post_id, record.comment_url,
                 record.created_at, record.like_count, record.collected_at))
            self.conn.execute("""INSERT INTO comment_metadata(platform, comment_id, subreddit)
                VALUES ('reddit', ?, ?)
                ON CONFLICT(platform, comment_id) DO UPDATE SET subreddit=excluded.subreddit""",
                (c.id, c.subreddit.lower() if c.subreddit else None))
        return "updated" if exists else "created"

    def purge(self, *, now: float | None = None, retention_hours: float = 48) -> int:
        if not math.isfinite(retention_hours) or retention_hours <= 0:
            raise ValueError("retention_hours phải > 0")
        cutoff = utc_text((now or time.time()) - retention_hours * 3600)
        with self.conn:
            return self.conn.execute(
                "DELETE FROM comments WHERE platform='reddit' AND collected_at <= ?", (cutoff,)
            ).rowcount


def stats(path: Path) -> dict:
    if not path.exists():
        return {"comments": 0, "subreddits": []}
    with sqlite3.connect(path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM comments WHERE platform='reddit'").fetchone()[0]
        metadata = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='comment_metadata'").fetchone()
        groups = [] if not metadata else [
            {"subreddit": name, "comments": count}
            for name, count in conn.execute("""SELECT subreddit, COUNT(*) FROM comment_metadata
                WHERE platform='reddit' GROUP BY subreddit ORDER BY subreddit""")]
        return {"comments": total, "subreddits": groups}


def show(path: Path, *, limit: int) -> int:
    if not path.is_file():
        raise ValueError("không tìm thấy database; kiểm tra đường dẫn --db")
    import json
    with sqlite3.connect(path) as conn:
        rows = conn.execute("""SELECT content FROM comments WHERE platform='reddit'
            ORDER BY collected_at DESC, comment_id DESC LIMIT ?""", (limit,)).fetchall()
    for index, (content,) in enumerate(rows, 1):
        print(f"{index}. {json.dumps(content, ensure_ascii=False)}")
    return len(rows)
