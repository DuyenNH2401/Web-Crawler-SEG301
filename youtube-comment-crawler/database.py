import csv
import json
import os
import sqlite3

import config

SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS comments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,

    platform      VARCHAR(20)  NOT NULL,
    comment_id    VARCHAR(255) NOT NULL,
    content       TEXT         NOT NULL,

    author_id     VARCHAR(255) NOT NULL,
    author_name   VARCHAR(255) NOT NULL,

    parent_id     VARCHAR(255) NOT NULL,
    post_id       VARCHAR(255) NOT NULL,
    comment_url   TEXT         NOT NULL,

    created_at    TIMESTAMP    NOT NULL,
    like_count    INTEGER      NOT NULL DEFAULT 0,

    collected_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(platform, comment_id)
);
CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(platform, post_id);
"""


class Database:
    def __init__(self, db_path=None):
        self.db_path = db_path or config.DB_PATH
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_SQLITE)
        self.conn.commit()

    def upsert_comments(self, records):
        """
        Cào trùng (platform, comment_id) đã có thì update like_count, content với
        collected_at.
        """
        columns = config.EXPORT_COLUMNS
        sql = f"""
            INSERT INTO comments ({", ".join(columns)})
            VALUES ({", ".join("?" for _ in columns)})
            ON CONFLICT(platform, comment_id) DO UPDATE SET
                content      = excluded.content,
                author_name  = excluded.author_name,
                like_count   = excluded.like_count,
                collected_at = excluded.collected_at
        """
        with self.conn:  
            self.conn.executemany(sql, [tuple(r[c] for c in columns) for r in records])

    def insert_comments(self, records):
        columns = config.EXPORT_COLUMNS
        sql = f"""
            INSERT INTO comments ({", ".join(columns)})
            VALUES ({", ".join("?" for _ in columns)})
            ON CONFLICT(platform, comment_id) DO NOTHING
        """
        before = self.conn.total_changes
        with self.conn:
            self.conn.executemany(sql, [tuple(r[c] for c in columns) for r in records])
        return self.conn.total_changes - before

    def get_post_comments(self, post_id, platform=None):
        return self.conn.execute(
            "SELECT comment_id, author_id, content FROM comments "
            "WHERE platform = ? AND post_id = ? ORDER BY id",
            (platform or config.PLATFORM, post_id),
        ).fetchall()

    def get_all_comments(self):
        return self.conn.execute(
            "SELECT comment_id, author_id, content FROM comments ORDER BY id"
        ).fetchall()

    def get_stats(self):
        cur = self.conn.cursor()
        total = cur.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
        roots = cur.execute(
            "SELECT COUNT(*) FROM comments WHERE parent_id = ?", (config.ROOT,)
        ).fetchone()[0]
        per_post = cur.execute(
            "SELECT platform, post_id, COUNT(*) AS n, MAX(collected_at) AS last "
            "FROM comments GROUP BY platform, post_id ORDER BY last DESC"
        ).fetchall()
        unknown_author = cur.execute(
            "SELECT COUNT(*) FROM comments WHERE author_id = ?", (config.UNKNOWN,)
        ).fetchone()[0]
        return {
            "total": total,
            "roots": roots,
            "replies": total - roots,
            "per_post": [dict(r) for r in per_post],
            "unknown_author": unknown_author,
        }

    def _select(self, post_id=None):
        sql = f"SELECT {', '.join(config.EXPORT_COLUMNS)} FROM comments"
        params = ()
        if post_id:
            sql += " WHERE post_id = ?"
            params = (post_id,)
        return self.conn.execute(sql + " ORDER BY id", params)

    def export_csv(self, path, post_id=None):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        count = 0
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(config.EXPORT_COLUMNS)
            for row in self._select(post_id):
                writer.writerow(list(row))
                count += 1
        return count

    def export_jsonl(self, path, post_id=None):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        count = 0
        with open(path, "w", encoding="utf-8") as f:
            for row in self._select(post_id):
                f.write(json.dumps(dict(row), ensure_ascii=False) + "\n")
                count += 1
        return count

    def close(self):
        self.conn.close()
