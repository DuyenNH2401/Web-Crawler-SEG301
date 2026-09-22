"""
reader.py - a read-only interface to the crawl database.

`database.Database` is the writer used during a crawl. This module is its
counterpart for everything afterwards: analysis, reporting, and the indexing
assignment that consumes this corpus.

Two things it does deliberately:

  - It opens the file **read-only**, so nothing that imports it can damage a
    crawl that took two minutes to collect.
  - It leaves the `content` column out of listings. Content averages ~6.7 KB
    per row, so `SELECT *` over 100 pages moves ~670 KB to build a list of
    titles. Content is fetched per-page, or streamed, only when asked for.

Typical use:

    from reader import CrawlReader

    with CrawlReader() as db:
        print(db.count_pages())
        for page in db.pages(depth=1, limit=10):
            print(page.title)
        article = db.page(316, with_content=True)
        print(article.content[:500])
"""

import os
import sqlite3
from dataclasses import dataclass, field

import config


# The listing columns - everything except the expensive `content` blob.
PAGE_COLUMNS = "id, url, domain, title, depth, status_code, crawled_at"


class DatabaseNotFound(Exception):
    """Raised when the database file does not exist yet."""


@dataclass
class Page:
    """
    One row of the `pages` table.

    `content` is None when the page was loaded from a listing, which is not the
    same as an empty string - that would mean the page genuinely had no text.
    Use `with_content=True` to populate it.
    """

    id: int
    url: str
    domain: str
    title: str
    depth: int
    status_code: int
    crawled_at: str
    content: str = field(default=None, repr=False)

    @property
    def has_content(self):
        return self.content is not None

    @property
    def content_length(self):
        return len(self.content) if self.content is not None else None

    def __str__(self):
        return f"[{self.id}] d{self.depth} {self.status_code} {self.title[:60]}"


def _to_page(row):
    """Build a Page from a sqlite3.Row, tolerating a missing content column."""
    keys = row.keys()
    return Page(
        id=row["id"],
        url=row["url"],
        domain=row["domain"],
        title=row["title"],
        depth=row["depth"],
        status_code=row["status_code"],
        crawled_at=row["crawled_at"],
        content=row["content"] if "content" in keys else None,
    )


class CrawlReader:
    """Read-only access to a crawl database."""

    def __init__(self, path=None):
        self.path = path or config.DATABASE_PATH
        if not os.path.exists(self.path):
            raise DatabaseNotFound(
                f"No database at {self.path!r}. Run `python main.py` first."
            )

        # The `mode=ro` URI is what enforces read-only; a plain connect() would
        # happily let a caller DELETE the corpus.
        uri = f"file:{self.path.replace(os.sep, '/')}?mode=ro"
        self.conn = sqlite3.connect(uri, uri=True)
        self.conn.row_factory = sqlite3.Row

    # -------------------------------------------------------- lifecycle ----
    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False

    # ------------------------------------------------------------ counts ---
    def count_pages(self):
        return self.conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]

    def count_links(self):
        return self.conn.execute("SELECT COUNT(*) FROM links").fetchone()[0]

    def is_empty(self):
        return self.count_pages() == 0

    # ----------------------------------------------------------- reading ---
    def page(self, page_id, with_content=False):
        """One page by id, or None. Content is loaded only when asked for."""
        columns = PAGE_COLUMNS + (", content" if with_content else "")
        row = self.conn.execute(
            f"SELECT {columns} FROM pages WHERE id = ?", (page_id,)
        ).fetchone()
        return _to_page(row) if row else None

    def page_by_url(self, url, with_content=False):
        """One page by exact URL, or None. URLs are stored normalized."""
        columns = PAGE_COLUMNS + (", content" if with_content else "")
        row = self.conn.execute(
            f"SELECT {columns} FROM pages WHERE url = ?", (url,)
        ).fetchone()
        return _to_page(row) if row else None

    def pages(self, depth=None, domain=None, status_code=None,
              limit=None, offset=0, with_content=False):
        """
        A filtered list of pages, ordered by id (which is crawl order, and so
        also breadth-first order).

        Every filter is applied as a bound parameter, never string-formatted
        into the SQL.
        """
        columns = PAGE_COLUMNS + (", content" if with_content else "")
        sql = f"SELECT {columns} FROM pages"
        clauses, params = [], []

        if depth is not None:
            clauses.append("depth = ?")
            params.append(depth)
        if domain is not None:
            clauses.append("domain = ?")
            params.append(domain)
        if status_code is not None:
            clauses.append("status_code = ?")
            params.append(status_code)

        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id"
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params += [limit, offset]

        return [_to_page(r) for r in self.conn.execute(sql, params)]

    def iter_pages(self, with_content=True, batch_size=25):
        """
        Stream every page, in batches, instead of building one large list.

        This is the method the indexing assignment should use: it keeps only
        `batch_size` documents in memory at a time, so the corpus can grow well
        past 100 pages without the whole thing being resident.
        """
        columns = PAGE_COLUMNS + (", content" if with_content else "")
        cursor = self.conn.execute(f"SELECT {columns} FROM pages ORDER BY id")
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                return
            for row in rows:
                yield _to_page(row)

    def search(self, term, in_content=False, limit=20):
        """
        Find pages whose title - or, with `in_content`, whose text - contains
        `term`, case-insensitively.

        The wildcards are bound as part of the *parameter*, so a term
        containing a quote cannot alter the query.
        """
        column = "content" if in_content else "title"
        rows = self.conn.execute(
            f"SELECT {PAGE_COLUMNS} FROM pages "
            f"WHERE {column} LIKE ? ORDER BY id LIMIT ?",
            (f"%{term}%", limit),
        )
        return [_to_page(r) for r in rows]

    # ------------------------------------------------------- distributions --
    def pages_per_depth(self):
        """{depth: count}, ordered by depth."""
        return {r[0]: r[1] for r in self.conn.execute(
            "SELECT depth, COUNT(*) FROM pages GROUP BY depth ORDER BY depth")}

    def pages_per_domain(self):
        return {r[0]: r[1] for r in self.conn.execute(
            "SELECT domain, COUNT(*) FROM pages GROUP BY domain "
            "ORDER BY COUNT(*) DESC")}

    def pages_per_status(self):
        return {r[0]: r[1] for r in self.conn.execute(
            "SELECT status_code, COUNT(*) FROM pages GROUP BY status_code "
            "ORDER BY status_code")}

    def content_stats(self):
        """min / average / maximum content length, and the truncation count."""
        row = self.conn.execute(
            "SELECT MIN(LENGTH(content)), CAST(AVG(LENGTH(content)) AS INT),"
            " MAX(LENGTH(content)) FROM pages"
        ).fetchone()
        truncated = self.conn.execute(
            "SELECT COUNT(*) FROM pages WHERE LENGTH(content) >= ?",
            (config.MAX_CONTENT_CHARS,),
        ).fetchone()[0] if config.MAX_CONTENT_CHARS else 0
        return {"min": row[0], "avg": row[1], "max": row[2], "truncated": truncated}

    # -------------------------------------------------------- the graph ----
    def outbound_links(self, url):
        """Every link found on `url`, in the order they appeared."""
        return [r[0] for r in self.conn.execute(
            "SELECT target_url FROM links WHERE source_url = ? ORDER BY id", (url,))]

    def inbound_links(self, url):
        """Every crawled page that links to `url`."""
        return [r[0] for r in self.conn.execute(
            "SELECT DISTINCT source_url FROM links WHERE target_url = ?", (url,))]

    def top_targets(self, limit=10, crawled_only=False):
        """
        The most-linked-to URLs, as (url, count) pairs.

        Without `crawled_only` the result is dominated by site navigation - the
        section menu appears on every page, so those targets score once per
        crawled page. Set it to restrict the ranking to pages actually stored,
        which is the ranking that means something.
        """
        if crawled_only:
            sql = ("SELECT l.target_url, COUNT(*) n FROM links l "
                   "JOIN pages p ON p.url = l.target_url "
                   "GROUP BY l.target_url ORDER BY n DESC LIMIT ?")
        else:
            sql = ("SELECT target_url, COUNT(*) n FROM links "
                   "GROUP BY target_url ORDER BY n DESC LIMIT ?")
        return [(r[0], r[1]) for r in self.conn.execute(sql, (limit,))]

    def link_count_for(self, url):
        return self.conn.execute(
            "SELECT COUNT(*) FROM links WHERE source_url = ?", (url,)).fetchone()[0]

    # ---------------------------------------------------------- metadata ---
    def tables(self):
        return [r[0] for r in self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name")]

    def schema(self, table=None):
        if table:
            row = self.conn.execute(
                "SELECT sql FROM sqlite_master WHERE name = ?", (table,)).fetchone()
            return row[0] if row else None
        return {r[0]: r[1] for r in self.conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE sql IS NOT NULL")}

    def columns(self, table):
        return [r[1] for r in self.conn.execute(f"PRAGMA table_info({table})")]

    # ------------------------------------------------------------ escape ---
    def sql(self, query, params=()):
        """
        Run an arbitrary read query and return a list of dicts.

        Writes are rejected by the connection itself, not by inspecting the
        query text, so there is no pattern here to work around.
        """
        return [dict(r) for r in self.conn.execute(query, params)]


# --------------------------------------------------------------------------
# Demonstration - `python reader.py`
# --------------------------------------------------------------------------
def _demo():
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    with CrawlReader() as db:
        if db.is_empty():
            print("The database is empty - run `python main.py` first.")
            return

        print(f"{db.path}: {db.count_pages()} pages, {db.count_links()} links")
        print(f"tables            : {db.tables()}")
        print(f"pages per depth   : {db.pages_per_depth()}")
        print(f"pages per domain  : {db.pages_per_domain()}")
        print(f"content stats     : {db.content_stats()}")

        print("\nfirst 3 pages at depth 1:")
        for page in db.pages(depth=1, limit=3):
            print(f"  {page}")

        print("\nmost-linked-to pages that were actually crawled:")
        for url, count in db.top_targets(limit=3, crawled_only=True):
            print(f"  {count:4}  {url[:72]}")

        first = db.pages(limit=1)[0]
        full = db.page(first.id, with_content=True)
        print(f"\ncontent of page {full.id} is {full.content_length} chars:")
        print(f"  {full.content[:200]}...")


if __name__ == "__main__":
    _demo()
