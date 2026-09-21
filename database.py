import os
import sqlite3

import config


class Database:
    def __init__(self, db_path=None):
        self.db_path = db_path or config.DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                domain TEXT,
                title TEXT,
                content TEXT,
                depth INTEGER,
                status_code INTEGER,
                crawled_at TEXT
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_url TEXT,
                target_url TEXT
            )
        """)
        self.conn.commit()

    def save_page(self, page_info):
        try:
            self.cursor.execute("""
                INSERT OR IGNORE INTO pages
                (url, domain, title, content, depth, status_code, crawled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                page_info["url"],
                page_info["domain"],
                page_info["title"],
                page_info["content"],
                page_info["depth"],
                page_info["status_code"],
                page_info["crawled_at"],
            ))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"[DB ERROR] Khong the luu page {page_info['url']}: {e}")
            return False

    def save_link(self, source_url, target_url):
        try:
            self.cursor.execute(
                "INSERT INTO links (source_url, target_url) VALUES (?, ?)",
                (source_url, target_url),
            )
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"[DB ERROR] Khong the luu link {source_url} -> {target_url}: {e}")

    def get_stats(self):
        self.cursor.execute("SELECT COUNT(*) FROM pages")
        total_pages = self.cursor.fetchone()[0]

        self.cursor.execute("SELECT COUNT(*) FROM links")
        total_links = self.cursor.fetchone()[0]

        self.cursor.execute("SELECT depth, COUNT(*) FROM pages GROUP BY depth")
        depth_counts = dict(self.cursor.fetchall())

        self.cursor.execute("SELECT status_code, COUNT(*) FROM pages GROUP BY status_code")
        status_counts = dict(self.cursor.fetchall())

        return {
            "total_pages": total_pages,
            "total_links": total_links,
            "depth_counts": depth_counts,
            "status_counts": status_counts,
        }

    def close(self):
        self.conn.close()
