"""Schema và thao tác SQLite; các hàm đọc không thay đổi database."""
from __future__ import annotations

from contextlib import closing
import json
import math
from pathlib import Path
import sqlite3
import time
from typing import Any

from .config import DEFAULT_RETENTION_HOURS, DELETED
from .models import Comment


COMMENT_COLUMNS = ("platform", "comment_id", "content", "author_id", "author_name", "parent_id",
                   "post_id", "comment_url", "created_at", "like_count", "collected_at")
LEGACY_COLUMNS = {"id", "post_id", "parent_id", "subreddit", "body", "score",
                  "created_utc", "edited_utc", "collected_at", "updated_at"}


class Store:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA secure_delete = ON")
        self.conn.execute("PRAGMA foreign_keys = ON")
        try:
            self.ensure_schema()
        except Exception:
            self.conn.close()
            raise

    def ensure_schema(self) -> None:
        columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(comments)")}
        legacy = columns == LEGACY_COLUMNS
        if columns and not legacy and columns != set(COMMENT_COLUMNS):
            raise ValueError("schema comments không được hỗ trợ; database chưa bị thay đổi")
        # Explicit BEGIN keeps DDL and data migration in the same transaction.
        self.conn.execute("BEGIN")
        with self.conn:
            if legacy:
                self.conn.execute("ALTER TABLE comments RENAME TO comments_legacy")
            self.conn.execute("""CREATE TABLE IF NOT EXISTS comments (
                platform TEXT NOT NULL CHECK(platform = 'reddit'),
                comment_id TEXT NOT NULL, content TEXT, author_id TEXT, author_name TEXT,
                parent_id TEXT, post_id TEXT, comment_url TEXT, created_at REAL,
                like_count INTEGER, collected_at REAL NOT NULL,
                PRIMARY KEY(platform, comment_id)
            )""")
            # Keep operational subreddit metadata outside the requested 11 columns.
            self.conn.execute("""CREATE TABLE IF NOT EXISTS comment_metadata (
                platform TEXT NOT NULL, comment_id TEXT NOT NULL, subreddit TEXT,
                PRIMARY KEY(platform, comment_id),
                FOREIGN KEY(platform, comment_id) REFERENCES comments(platform, comment_id) ON DELETE CASCADE
            )""")
            if legacy:
                self.conn.execute("""INSERT INTO comments
                    SELECT 'reddit', id, body, NULL, NULL, parent_id,
                        CASE WHEN substr(post_id, 1, 3) = 't3_' THEN post_id ELSE 't3_' || post_id END,
                        NULL, created_utc, score, collected_at FROM comments_legacy""")
                self.conn.execute("""INSERT INTO comment_metadata
                    SELECT 'reddit', id, subreddit FROM comments_legacy""")
                self.conn.execute("DROP TABLE comments_legacy")
            self.conn.execute("CREATE INDEX IF NOT EXISTS comments_collected ON comments(collected_at)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS metadata_subreddit ON comment_metadata(subreddit)")

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def close(self) -> None:
        self.conn.close()

    def ids(self) -> list[str]:
        return [row[0] for row in self.conn.execute("SELECT comment_id FROM comments WHERE platform='reddit' ORDER BY comment_id")]

    def delete(self, cid: str) -> int:
        with self.conn:
            return self.conn.execute("DELETE FROM comments WHERE platform='reddit' AND comment_id = ?", (cid,)).rowcount

    def save(self, value: Any, *, now: float | None = None) -> str:
        c = Comment.from_value(value)
        if c.body in DELETED:
            return "deleted" if self.delete(c.id) else "skipped"
        now = time.time() if now is None else now
        with self.conn:
            exists = self.conn.execute("SELECT 1 FROM comments WHERE platform='reddit' AND comment_id = ?", (c.id,)).fetchone()
            self.conn.execute("""INSERT INTO comments
                (platform, comment_id, content, author_id, author_name, parent_id,
                 post_id, comment_url, created_at, like_count, collected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(platform, comment_id) DO UPDATE SET content=excluded.content,
                author_id=excluded.author_id, author_name=excluded.author_name,
                parent_id=excluded.parent_id, post_id=excluded.post_id,
                comment_url=excluded.comment_url, created_at=excluded.created_at,
                like_count=excluded.like_count""",
                ("reddit", c.id, c.body, c.author_id, c.author_name, c.parent_id, c.post_id,
                 c.comment_url, c.created_utc, c.score, now))
            self.conn.execute("""INSERT INTO comment_metadata VALUES ('reddit', ?, ?)
                ON CONFLICT(platform, comment_id) DO UPDATE SET subreddit=excluded.subreddit""",
                (c.id, c.subreddit.lower() if c.subreddit else None))
        return "updated" if exists else "created"

    def purge(self, *, now: float | None = None, retention_hours: float = DEFAULT_RETENTION_HOURS) -> int:
        if not math.isfinite(retention_hours) or retention_hours <= 0:
            raise ValueError("retention_hours phải > 0")
        now = time.time() if now is None else now
        with self.conn:
            return self.conn.execute("DELETE FROM comments WHERE collected_at <= ?",
                                     (now - retention_hours * 3600,)).rowcount


def show_comments(path: Path, *, limit: int) -> int:
    """Print a bounded list without creating, migrating or purging the database."""
    if not path.is_file():
        raise ValueError("không tìm thấy database; kiểm tra đường dẫn --db")
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(comments)")}
        if columns == LEGACY_COLUMNS:
            content_column, id_column = "body", "id"
        elif columns == set(COMMENT_COLUMNS):
            content_column, id_column = "content", "comment_id"
        else:
            raise ValueError("database có schema comments không được hỗ trợ")
        rows = conn.execute(f"SELECT {content_column} FROM comments "
                            f"ORDER BY collected_at DESC, {id_column} DESC LIMIT ?", (limit,))
        count = 0
        for count, (content,) in enumerate(rows, start=1):
            # JSON string escaping keeps multiline comments on one terminal line.
            text = "None" if content is None else json.dumps(content, ensure_ascii=False)
            print(f"{count}. {text}")
    return count


def database_stats(path: Path) -> dict[str, Any]:
    """Đếm comment và nhóm theo subreddit, không tạo hoặc sửa database."""
    if not path.exists():
        return dict(comments=0, subreddits=[])
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(comments)")}
        table = "comments" if columns == LEGACY_COLUMNS else "comment_metadata"
        return dict(comments=conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0],
                    subreddits=[dict(subreddit=name, comments=count) for name, count in
                                conn.execute(f"SELECT subreddit, COUNT(*) FROM {table} GROUP BY subreddit")])
