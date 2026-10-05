"""A local SQLite database plus UTF-8 JSONL/CSV exports."""

import csv
import hashlib
import json
import sqlite3
from dataclasses import asdict, fields
from pathlib import Path

from crawler.common.models import Comment, ParsedThread, Post


class DatasetStore:
    def __init__(self, output: Path):
        self.output = output
        output.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(output / "dataset.sqlite3")
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS posts (
                platform TEXT NOT NULL, post_id TEXT NOT NULL,
                post_url TEXT NOT NULL, content TEXT NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY (platform, post_id)
            );
            CREATE TABLE IF NOT EXISTS comments (
                platform TEXT NOT NULL, comment_id TEXT NOT NULL,
                post_id TEXT NOT NULL, parent_id TEXT NOT NULL,
                content TEXT NOT NULL CHECK (length(content) > 0), payload TEXT NOT NULL,
                PRIMARY KEY (platform, comment_id, post_id),
                FOREIGN KEY (platform, post_id) REFERENCES posts(platform, post_id)
            );
            CREATE TABLE IF NOT EXISTS crawl_runs (
                run_id TEXT PRIMARY KEY, manifest TEXT NOT NULL
            );
        """)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.connection.close()

    def snapshot(self, html: str, label: str) -> Path:
        folder = self.output / "raw_html"
        folder.mkdir(exist_ok=True)
        digest = hashlib.sha256(html.encode("utf-8")).hexdigest()
        path = folder / f"{label}_{digest[:16]}.html"
        path.write_text(html, encoding="utf-8")
        return path

    def save(self, thread: ParsedThread, comment_limit: int | None = None) -> None:
        post = thread.post
        if not post.post_id or not post.post_url:
            raise ValueError("Post identity is missing.")
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO posts VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (platform, post_id) DO UPDATE SET
                    post_url=excluded.post_url, content=excluded.content, payload=excluded.payload
            """,
                (
                    post.platform,
                    post.post_id,
                    post.post_url,
                    post.content,
                    json.dumps(asdict(post), ensure_ascii=False),
                ),
            )
            for comment in thread.comments[:comment_limit]:
                if (
                    not comment.content.strip()
                    or not comment.comment_id
                    or not comment.comment_url
                ):
                    raise ValueError("Comment text or identity is missing.")
                if comment.post_id != post.post_id:
                    raise ValueError("Comment references a different post.")
                if comment.like_count is not None and comment.like_count < 0:
                    raise ValueError("Negative like count.")
                self.connection.execute(
                    """
                    INSERT INTO comments VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT (platform, comment_id, post_id) DO UPDATE SET
                        parent_id=excluded.parent_id, content=excluded.content, payload=excluded.payload
                """,
                    (
                        comment.platform,
                        comment.comment_id,
                        comment.post_id,
                        comment.parent_id,
                        comment.content,
                        json.dumps(asdict(comment), ensure_ascii=False),
                    ),
                )

    def save_run(self, manifest: dict) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO crawl_runs VALUES (?, ?)",
                (manifest["run_id"], json.dumps(manifest, ensure_ascii=False)),
            )
        folder = self.output / "runs"
        folder.mkdir(exist_ok=True)
        (folder / f"{manifest['run_id']}.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get_post(self, post_id: str) -> Post | None:
        row = self.connection.execute(
            "SELECT payload FROM posts WHERE platform='threads' AND post_id=?",
            (post_id,),
        ).fetchone()
        return Post(**json.loads(row[0])) if row else None

    def comment_ids(self, post_id: str) -> set[str]:
        return {
            row[0]
            for row in self.connection.execute(
                "SELECT comment_id FROM comments WHERE platform='threads' AND post_id=?",
                (post_id,),
            )
        }

    def comment_count(self, post_id: str) -> int:
        return self.connection.execute(
            "SELECT count(*) FROM comments WHERE platform='threads' AND post_id=?",
            (post_id,),
        ).fetchone()[0]

    def export(self) -> dict[str, int]:
        folder = self.output / "exports"
        folder.mkdir(exist_ok=True)
        counts = {}
        for table, model in [("posts", Post), ("comments", Comment)]:
            columns = [f.name for f in fields(model)]
            counts[table] = 0
            with (
                (folder / f"{table}.jsonl").open("w", encoding="utf-8") as jsonl,
                (folder / f"{table}.csv").open(
                    "w", encoding="utf-8-sig", newline=""
                ) as csvfile,
            ):
                writer = csv.DictWriter(csvfile, fieldnames=columns)
                writer.writeheader()
                for (payload,) in self.connection.execute(
                    f"SELECT payload FROM {table} ORDER BY rowid"
                ):
                    record = json.loads(payload)
                    writer.writerow(record)
                    jsonl.write(json.dumps(record, ensure_ascii=False) + "\n")
                    counts[table] += 1
        return counts
