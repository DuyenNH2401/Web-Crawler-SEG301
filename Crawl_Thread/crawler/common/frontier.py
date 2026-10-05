"""Durable BFS frontier: visit the lowest depth, then use discovery order."""

import json
import sqlite3
from dataclasses import dataclass

from crawler.common.models import Post, utc_now


@dataclass(frozen=True)
class CrawlJob:
    id: int
    url: str
    kind: str
    depth: int
    root_url: str
    discovered_from: str


class Frontier:
    def __init__(
        self,
        connection: sqlite3.Connection,
        session: str,
        options: dict,
        resume: bool = False,
    ):
        self.db = connection
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS bfs_sessions (
                id TEXT PRIMARY KEY, options TEXT NOT NULL, started_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS bfs_frontier (
                id INTEGER PRIMARY KEY, session TEXT NOT NULL,
                url TEXT NOT NULL, kind TEXT NOT NULL, depth INTEGER NOT NULL,
                root_url TEXT NOT NULL, discovered_from TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending', error TEXT,
                UNIQUE(session, url, root_url)
            );
            CREATE TABLE IF NOT EXISTS bfs_pages (
                session TEXT NOT NULL, url TEXT NOT NULL,
                snapshots TEXT NOT NULL DEFAULT '[]', error TEXT, completed INTEGER NOT NULL,
                PRIMARY KEY(session, url)
            );
            CREATE TABLE IF NOT EXISTS bfs_candidates (
                session TEXT NOT NULL, url TEXT NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY(session, url)
            );
        """)
        if resume:
            row = self.db.execute(
                "SELECT id, options FROM bfs_sessions ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
            if row is None:
                raise ValueError("No BFS crawl to resume in this output directory.")
            self.session, stored = row
            self.options = json.loads(stored)
            with self.db:
                self.db.execute(
                    "UPDATE bfs_frontier SET status='pending' WHERE session=? AND status='processing'",
                    (self.session,),
                )
        else:
            self.session, self.options = session, options
            with self.db:
                self.db.execute(
                    "INSERT INTO bfs_sessions VALUES (?, ?, ?)",
                    (session, json.dumps(options, ensure_ascii=False), utc_now()),
                )

    def enqueue(
        self,
        url: str,
        kind: str,
        depth: int,
        root_url: str = "",
        discovered_from: str = "",
    ) -> bool:
        with self.db:
            cursor = self.db.execute(
                """
                INSERT OR IGNORE INTO bfs_frontier
                (session,url,kind,depth,root_url,discovered_from) VALUES (?,?,?,?,?,?)
            """,
                (self.session, url, kind, depth, root_url, discovered_from),
            )
        return bool(cursor.rowcount)

    def peek(self) -> CrawlJob | None:
        row = self.db.execute(
            """
            SELECT id,url,kind,depth,root_url,discovered_from FROM bfs_frontier
            WHERE session=? AND status='pending' ORDER BY depth,id LIMIT 1
        """,
            (self.session,),
        ).fetchone()
        return CrawlJob(*row) if row else None

    def mark(self, job: CrawlJob, status: str, error: str | None = None):
        with self.db:
            self.db.execute(
                "UPDATE bfs_frontier SET status=?,error=? WHERE id=?",
                (status, error, job.id),
            )

    def retry_errors(self):
        with self.db:
            # Failed fetches need fresh pages. Parser-only failures can reuse
            # their saved snapshots, e.g. after fixing an empty-results bug.
            self.db.execute(
                "UPDATE bfs_pages SET completed=0,error=NULL WHERE session=? AND error IS NOT NULL",
                (self.session,),
            )
            self.db.execute(
                "UPDATE bfs_frontier SET status='pending',error=NULL WHERE session=? AND status='error'",
                (self.session,),
            )

    def pages(self, url: str) -> tuple[list[str], str | None] | None:
        row = self.db.execute(
            "SELECT snapshots,error FROM bfs_pages WHERE session=? AND url=? AND completed=1",
            (self.session, url),
        ).fetchone()
        return (json.loads(row[0]), row[1]) if row else None

    def cache(
        self,
        url: str,
        snapshots: list[str],
        error: str | None = None,
        completed: bool = True,
    ):
        with self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO bfs_pages VALUES (?,?,?,?,?)",
                (self.session, url, json.dumps(snapshots), error, int(completed)),
            )

    def was_attempted(self, url: str) -> bool:
        return (
            self.db.execute(
                "SELECT 1 FROM bfs_pages WHERE session=? AND url=?", (self.session, url)
            ).fetchone()
            is not None
        )

    def candidate(self, post: Post):
        from dataclasses import asdict

        with self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO bfs_candidates VALUES (?,?,?)",
                (
                    self.session,
                    post.post_url,
                    json.dumps(asdict(post), ensure_ascii=False),
                ),
            )

    def candidates(self) -> dict[str, Post]:
        records = self.db.execute(
            "SELECT payload FROM bfs_candidates WHERE session=? ORDER BY rowid",
            (self.session,),
        )
        posts = [Post(**json.loads(row[0])) for row in records]
        return {p.post_id: p for p in posts}

    def count(self, kind: str | None = None) -> int:
        sql = "SELECT count(*) FROM bfs_frontier WHERE session=?"
        params = [self.session]
        if kind:
            sql += " AND kind=?"
            params.append(kind)
        return self.db.execute(sql, params).fetchone()[0]

    def fetched_count(self) -> int:
        return self.db.execute(
            "SELECT count(*) FROM bfs_pages WHERE session=?", (self.session,)
        ).fetchone()[0]

    def stats(self) -> dict:
        statuses = dict(
            self.db.execute(
                "SELECT status,count(*) FROM bfs_frontier WHERE session=? GROUP BY status",
                (self.session,),
            )
        )
        return {
            "session_id": self.session,
            "unique_urls_fetched": self.fetched_count(),
            "jobs": statuses,
            "pending": statuses.get("pending", 0),
        }
