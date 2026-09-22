"""
database.py - Task 8: storing crawl results in SQLite.
"""

import os
import sqlite3


SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    url         TEXT UNIQUE,
    domain      TEXT,
    title       TEXT,
    content     TEXT,
    depth       INTEGER,
    status_code INTEGER,
    crawled_at  TEXT
);

CREATE TABLE IF NOT EXISTS links (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url TEXT,
    target_url TEXT
);

CREATE INDEX IF NOT EXISTS idx_links_source ON links(source_url);
CREATE INDEX IF NOT EXISTS idx_pages_depth  ON pages(depth);
"""


class Database:
    def __init__(self, path):
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ------------------------------------------------------------ writing --
    def save_page(self, page):
        """
        Insert one page record. `url` is UNIQUE, so INSERT OR IGNORE makes a
        repeated URL harmless even if the in-memory duplicate check is bypassed.
        Returns True when a row was actually inserted.
        """
        cur = self.conn.execute(
            """INSERT OR IGNORE INTO pages
               (url, domain, title, content, depth, status_code, crawled_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (page["url"], page["domain"], page["title"], page["content"],
             page["depth"], page["status_code"], page["crawled_at"]),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def save_links(self, source_url, target_urls):
        if not target_urls:
            return
        self.conn.executemany(
            "INSERT INTO links (source_url, target_url) VALUES (?, ?)",
            [(source_url, target) for target in target_urls],
        )
        self.conn.commit()

    def clear(self):
        """Start a fresh run without deleting the database file."""
        self.conn.executescript("DELETE FROM pages; DELETE FROM links;")
        self.conn.commit()

    # ------------------------------------------------------------ reading --
    def count_pages(self):
        return self.conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]

    def count_links(self):
        return self.conn.execute("SELECT COUNT(*) FROM links").fetchone()[0]

    def pages_per_depth(self):
        return self.conn.execute(
            "SELECT depth, COUNT(*) FROM pages GROUP BY depth ORDER BY depth"
        ).fetchall()

    def pages_per_domain(self):
        return self.conn.execute(
            "SELECT domain, COUNT(*) FROM pages GROUP BY domain ORDER BY COUNT(*) DESC"
        ).fetchall()

    def close(self):
        self.conn.close()
