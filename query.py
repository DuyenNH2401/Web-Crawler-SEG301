"""
query.py - inspect the crawl database.

A convenience wrapper around the standard-library sqlite3 module, so the
database can be examined without installing the sqlite3 command-line tool.

Usage:
    python query.py                      # overview of what was collected
    python query.py pages                # the stored pages, one line each
    python query.py links                # most-linked-to targets
    python query.py schema               # table definitions
    python query.py "SELECT ..."         # any SQL you like
"""

import sqlite3
import sys

import config

# Windows consoles default to cp1252, which cannot print Guardian headlines.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def connect():
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def print_table(rows, max_width=60):
    """Print query results as an aligned table."""
    if not rows:
        print("(no rows)")
        return

    headers = rows[0].keys()
    cells = [
        [str(r[h]).replace("\n", " ")[:max_width] for h in headers]
        for r in rows
    ]
    widths = [
        max(len(h), max(len(row[i]) for row in cells))
        for i, h in enumerate(headers)
    ]

    line = "  ".join(h.ljust(w) for h, w in zip(headers, widths))
    print(line)
    print("-" * len(line))
    for row in cells:
        print("  ".join(c.ljust(w) for c, w in zip(row, widths)))
    print(f"\n({len(rows)} row{'s' if len(rows) != 1 else ''})")


def overview(conn):
    total = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
    if total == 0:
        print("The database is empty - run `python main.py` first.")
        return

    print("=" * 52)
    print(f"  {config.DATABASE_PATH}")
    print("=" * 52)
    print(f"Pages stored          : {total}")
    print(f"Links recorded        : {conn.execute('SELECT COUNT(*) FROM links').fetchone()[0]}")
    print(f"Distinct link targets : {conn.execute('SELECT COUNT(DISTINCT target_url) FROM links').fetchone()[0]}")

    print("\nPages per depth:")
    for row in conn.execute("SELECT depth, COUNT(*) n FROM pages GROUP BY depth ORDER BY depth"):
        print(f"  depth {row['depth']}: {row['n']}")

    print("\nPages per domain:")
    for row in conn.execute("SELECT domain, COUNT(*) n FROM pages GROUP BY domain ORDER BY n DESC"):
        print(f"  {row['domain']}: {row['n']}")

    print("\nHTTP status codes:")
    for row in conn.execute("SELECT status_code, COUNT(*) n FROM pages GROUP BY status_code"):
        print(f"  {row['status_code']}: {row['n']}")

    row = conn.execute(
        "SELECT MIN(LENGTH(content)) lo, MAX(LENGTH(content)) hi,"
        " CAST(AVG(LENGTH(content)) AS INT) avg FROM pages"
    ).fetchone()
    print(f"\nContent length (chars): min {row['lo']}, avg {row['avg']}, max {row['hi']}")
    print(f"Crawl window          : "
          f"{conn.execute('SELECT MIN(crawled_at) FROM pages').fetchone()[0]}"
          f" -> {conn.execute('SELECT MAX(crawled_at) FROM pages').fetchone()[0]}")
    print("\nTry: python query.py pages | links | schema | \"SELECT ...\"")


PRESETS = {
    "pages": "SELECT id, depth, status_code, title, url FROM pages ORDER BY id",
    "links": """SELECT target_url, COUNT(*) AS times_linked
                FROM links GROUP BY target_url
                ORDER BY times_linked DESC LIMIT 25""",
    "schema": "SELECT type, name, sql FROM sqlite_master WHERE sql IS NOT NULL",
}


def main():
    conn = connect()
    try:
        if len(sys.argv) < 2:
            overview(conn)
            return 0

        argument = sys.argv[1]
        sql = PRESETS.get(argument, argument)

        try:
            print_table(conn.execute(sql).fetchall())
        except sqlite3.Error as error:
            print(f"SQL error: {error}")
            return 1
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
