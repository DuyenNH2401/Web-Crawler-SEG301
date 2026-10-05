"""Import existing crawler databases into the unified SQLite file."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import json
import sqlite3

import database
from shared_reddit import utc_text


ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "data" / "comments.db"
SOURCES = (
    ("reddit", ROOT / "reddit-crawler" / "data" / "reddit.sqlite3"),
    ("youtube", ROOT / "youtube-crawler" / "data" / "comments.db"),
)
TIKTOK_SOURCE = ROOT / "comments.db"
THREADS_DIR = ROOT / "Crawl_Thread" / "data"
COLUMNS = ("platform", "comment_id", "content", "author_id", "author_name",
           "parent_id", "post_id", "comment_url", "created_at", "like_count", "collected_at")


def import_existing(db_path: str | Path) -> dict[str, int]:
    """Copy old rows once, without replacing rows already present in the shared DB."""
    target = Path(db_path).resolve()
    database.init_comments_db(str(target))
    copied: dict[str, int] = {}
    with closing(database.get_connection(str(target))) as dest:
        with dest:
            dest.execute("""CREATE TABLE IF NOT EXISTS comment_metadata (
                platform TEXT NOT NULL, comment_id TEXT NOT NULL, subreddit TEXT,
                PRIMARY KEY(platform, comment_id),
                FOREIGN KEY(platform, comment_id) REFERENCES comments(platform, comment_id)
                    ON DELETE CASCADE)""")
        for platform, source_path in SOURCES:
            if not source_path.is_file() or source_path.resolve() == target:
                copied[platform] = 0
                continue
            with closing(sqlite3.connect(source_path)) as source:
                source.row_factory = sqlite3.Row
                rows = source.execute(
                    "SELECT * FROM comments WHERE platform=?", (platform,))
                count = 0
                with dest:
                    for row in rows:
                        values = [row[column] for column in COLUMNS]
                        if platform == "reddit":
                            for index in (2, 3, 4, 5, 6, 7):
                                values[index] = values[index] or ("UNKNOWN" if index in (3, 4, 5, 6) else "")
                            values[8] = utc_text(values[8])
                            values[9] = max(0, values[9] or 0)
                            values[10] = utc_text(values[10])
                        placeholders = ",".join("?" for _ in COLUMNS)
                        inserted = dest.execute(
                            f"INSERT OR IGNORE INTO comments ({','.join(COLUMNS)}) "
                            f"VALUES ({placeholders})", values).rowcount
                        count += inserted
                    if platform == "reddit":
                        table = source.execute("""SELECT 1 FROM sqlite_master
                            WHERE type='table' AND name='comment_metadata'""").fetchone()
                        if table:
                            for cid, subreddit in source.execute(
                                "SELECT comment_id, subreddit FROM comment_metadata WHERE platform='reddit'"):
                                dest.execute("""INSERT OR IGNORE INTO comment_metadata
                                    (platform, comment_id, subreddit) VALUES ('reddit', ?, ?)""",
                                    (cid, subreddit))
                copied[platform] = count
    copied["tiktok"] = import_tiktok_database(target, TIKTOK_SOURCE)
    copied["threads"] = 0
    if THREADS_DIR.is_dir():
        for source in THREADS_DIR.rglob("dataset.sqlite3"):
            copied["threads"] += import_threads_dataset(target, source)
    return copied


def import_tiktok_database(db_path: str | Path, source_path: str | Path) -> int:
    """Import the original TikTok database, whose schema lacks comment_url."""
    target, source_path = Path(db_path).resolve(), Path(source_path).resolve()
    if not source_path.is_file() or source_path == target:
        return 0
    database.init_comments_db(str(target))
    count = 0
    with closing(sqlite3.connect(source_path)) as source, closing(database.get_connection(str(target))) as dest:
        source.row_factory = sqlite3.Row
        with dest:
            for row in source.execute("SELECT * FROM comments WHERE platform='tiktok'"):
                values = (
                    "tiktok", row["comment_id"], row["content"] or "",
                    row["author_id"] or "UNKNOWN", row["author_name"] or "UNKNOWN",
                    row["parent_id"] or "ROOT", row["post_id"] or "UNKNOWN", "",
                    _time_text(row["created_at"]), max(0, row["like_count"] or 0),
                    _time_text(row["collected_at"]),
                )
                count += dest.execute(
                    f"INSERT OR IGNORE INTO comments ({','.join(COLUMNS)}) VALUES ({','.join('?' for _ in COLUMNS)})",
                    values).rowcount
    return count


def _time_text(value) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)):
        return utc_text(value)
    text = str(value)
    return text.replace(" ", "T") + "Z" if "T" not in text else text


def import_threads_dataset(db_path: str | Path, source_path: str | Path) -> int:
    """Copy Threads comments into the common table and retain all post contexts."""
    target, source_path = Path(db_path).resolve(), Path(source_path).resolve()
    if not source_path.is_file() or source_path == target:
        return 0
    database.init_comments_db(str(target))
    count = 0
    with closing(sqlite3.connect(source_path)) as source, closing(database.get_connection(str(target))) as dest:
        with dest:
            dest.execute("""CREATE TABLE IF NOT EXISTS threads_comment_context (
                comment_id TEXT NOT NULL, post_id TEXT NOT NULL,
                PRIMARY KEY(comment_id, post_id))""")
            for cid, post_id, payload in source.execute(
                "SELECT comment_id, post_id, payload FROM comments WHERE platform='threads' ORDER BY rowid"):
                raw = json.loads(payload)
                if not cid or not raw.get("content"):
                    continue
                values = (
                    "threads", cid, raw["content"], raw.get("author_id") or "UNKNOWN",
                    raw.get("author_name") or "UNKNOWN", raw.get("parent_id") or "UNKNOWN",
                    post_id, raw.get("comment_url") or "", _time_text(raw.get("created_at")),
                    max(0, raw.get("like_count") or 0), _time_text(raw.get("collected_at")),
                )
                count += dest.execute(
                    f"INSERT OR IGNORE INTO comments ({','.join(COLUMNS)}) VALUES ({','.join('?' for _ in COLUMNS)})",
                    values).rowcount
                dest.execute("INSERT OR IGNORE INTO threads_comment_context VALUES (?, ?)",
                             (cid, post_id))
    return count
