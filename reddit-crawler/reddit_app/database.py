"""Quản lý cơ sở dữ liệu SQLite lưu trữ comments."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import time
from typing import Any

from .parser import DELETED, normalize_comment

DEFAULT_DB = Path("data/reddit.sqlite3")


class Store:
    """Quản lý kết nối SQLite và lưu comment."""

    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("""CREATE TABLE IF NOT EXISTS comments (
            platform TEXT NOT NULL CHECK(platform = 'reddit'),
            comment_id TEXT NOT NULL,
            content TEXT, author_id TEXT, author_name TEXT,
            parent_id TEXT, post_id TEXT, comment_url TEXT,
            created_at REAL, like_count INTEGER, collected_at REAL NOT NULL,
            PRIMARY KEY(platform, comment_id)
        )""")
        self.conn.execute("""CREATE TABLE IF NOT EXISTS comment_metadata (
            platform TEXT NOT NULL, comment_id TEXT NOT NULL, subreddit TEXT,
            PRIMARY KEY(platform, comment_id)
        )""")

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def ids(self) -> list[str]:
        return [row[0] for row in self.conn.execute("SELECT comment_id FROM comments WHERE platform = 'reddit' ORDER BY comment_id")]

    def save(self, c: dict[str, Any], *, now: float | None = None) -> str:
        c = normalize_comment(c)
        cid = c["comment_id"]
        body = c["content"]
        if body in DELETED:
            with self.conn:
                del_count = self.conn.execute("DELETE FROM comments WHERE platform = 'reddit' AND comment_id = ?", (cid,)).rowcount
                self.conn.execute("DELETE FROM comment_metadata WHERE platform = 'reddit' AND comment_id = ?", (cid,))
            return "deleted" if del_count else "skipped"

        now = time.time() if now is None else now
        with self.conn:
            exists = self.conn.execute("SELECT 1 FROM comments WHERE platform = 'reddit' AND comment_id = ?", (cid,)).fetchone()
            self.conn.execute("""INSERT INTO comments
                (platform, comment_id, content, author_id, author_name, parent_id, post_id, comment_url, created_at, like_count, collected_at)
                VALUES ('reddit', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(platform, comment_id) DO UPDATE SET
                    content=excluded.content, author_id=excluded.author_id, author_name=excluded.author_name,
                    parent_id=excluded.parent_id, post_id=excluded.post_id, comment_url=excluded.comment_url,
                    created_at=excluded.created_at, like_count=excluded.like_count""",
                (cid, body, c["author_id"], c["author_name"], c["parent_id"], c["post_id"], c["comment_url"], c["created_at"], c["like_count"], now))
            sub = c.get("subreddit")
            if sub:
                self.conn.execute("""INSERT INTO comment_metadata (platform, comment_id, subreddit)
                    VALUES ('reddit', ?, ?)
                    ON CONFLICT(platform, comment_id) DO UPDATE SET subreddit=excluded.subreddit""",
                    (cid, sub))
        return "updated" if exists else "created"


def show_comments(path: Path, *, limit: int = 10) -> int:
    if not Path(path).exists():
        raise ValueError("Không tìm thấy database")
    with sqlite3.connect(path) as conn:
        rows = conn.execute("SELECT content FROM comments ORDER BY collected_at DESC, comment_id DESC LIMIT ?", (limit,)).fetchall()
        for idx, (content,) in enumerate(rows, 1):
            text = "None" if content is None else json.dumps(content, ensure_ascii=False)
            print(f"{idx}. {text}")
        return len(rows)


def database_stats(path: Path) -> dict[str, Any]:
    if not Path(path).exists():
        return dict(comments=0, subreddits=[])
    with sqlite3.connect(path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
        subs = [dict(subreddit=s, comments=c) for s, c in
                conn.execute("SELECT subreddit, COUNT(*) FROM comment_metadata GROUP BY subreddit").fetchall()]
        return dict(comments=total, subreddits=subs)
