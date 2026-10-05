"""Store social comments from all crawlers in one SQLite table."""

import os
import sqlite3
from contextlib import closing
from typing import Sequence

from models import Comment


def get_connection(db_path: str) -> sqlite3.Connection:
    """Open a database connection and create its parent directory if needed."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_comments_db(db_path: str) -> None:
    """Create the comments table and lookup index."""
    with closing(get_connection(db_path)) as conn, conn:
        ensure_comments_schema(conn)


def ensure_comments_schema(conn: sqlite3.Connection) -> None:
    """Create the shared schema on an existing connection, including in-memory DBs."""
    conn.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                comment_id TEXT NOT NULL,
                content TEXT NOT NULL,
                author_id TEXT NOT NULL,
                author_name TEXT NOT NULL,
                parent_id TEXT NOT NULL,
                post_id TEXT NOT NULL,
                comment_url TEXT NOT NULL,
                created_at TEXT NOT NULL,
                like_count INTEGER NOT NULL DEFAULT 0 CHECK (like_count >= 0),
                collected_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                UNIQUE (platform, comment_id)
            )
        """)
    conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_comments_platform_post
            ON comments (platform, post_id)
        """)


def upsert_comments(db_path: str, comments: Sequence[Comment]) -> int:
    """Insert or refresh comments, keyed by platform and comment ID."""
    if not comments:
        return 0
    init_comments_db(db_path)
    sql = """
        INSERT INTO comments (
            platform, comment_id, content, author_id, author_name, parent_id,
            post_id, comment_url, created_at, like_count, collected_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(platform, comment_id) DO UPDATE SET
            content=excluded.content,
            author_id=CASE WHEN excluded.author_id = 'UNKNOWN'
                THEN comments.author_id ELSE excluded.author_id END,
            author_name=excluded.author_name,
            parent_id=CASE WHEN excluded.parent_id = 'UNKNOWN'
                THEN comments.parent_id ELSE excluded.parent_id END,
            post_id=excluded.post_id,
            comment_url=excluded.comment_url,
            created_at=excluded.created_at,
            like_count=CASE WHEN excluded.parent_id = 'UNKNOWN'
                THEN comments.like_count ELSE excluded.like_count END,
            collected_at=excluded.collected_at
    """
    rows = [(
        c.platform, c.comment_id, c.content, c.author_id, c.author_name,
        c.parent_id, c.post_id, c.comment_url, c.created_at, c.like_count,
        c.collected_at,
    ) for c in comments]
    with closing(get_connection(db_path)) as conn, conn:
        conn.executemany(sql, rows)
    return len(rows)


def get_comments(db_path: str, platform: str, post_ids: Sequence[str]) -> list[sqlite3.Row]:
    """Read comments for the requested posts in a stable export order."""
    if not post_ids or not os.path.exists(db_path):
        return []
    placeholders = ",".join("?" for _ in post_ids)
    with closing(get_connection(db_path)) as conn:
        return conn.execute(
            f"SELECT * FROM comments WHERE platform = ? AND post_id IN ({placeholders}) "
            "ORDER BY created_at, id",
            [platform, *post_ids],
        ).fetchall()
