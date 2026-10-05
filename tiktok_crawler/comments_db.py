"""Map TikTok comments and CSV imports to the shared comments table."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path

import database
from models import Comment


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT_DIR / "data" / "comments.db"


def to_db_row(raw: dict, platform: str = "tiktok", post_id: str = "") -> Comment:
    cid = str(raw["cid"])
    video_id = str(raw.get("post_id") or post_id or "UNKNOWN")
    username = str(raw.get("username") or "")
    collected_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    created = str(raw.get("created_at") or "").strip()
    if created and "T" not in created:
        created = created.replace(" ", "T") + "Z"
    return Comment(
        platform=platform, comment_id=cid, content=str(raw.get("text") or ""),
        author_id=str(raw.get("author_id") or username or "UNKNOWN"),
        author_name=username or str(raw.get("nickname") or "UNKNOWN"),
        parent_id=str(raw.get("parent_cid") or "ROOT"), post_id=video_id,
        comment_url="", created_at=created or "1970-01-01T00:00:00Z",
        like_count=max(0, int(raw.get("likes") or 0)), collected_at=collected_at,
    )


def save_comments(rows, db_path, platform: str = "tiktok", post_id: str = "") -> int:
    records = [to_db_row(row, platform, post_id) for row in rows if row.get("cid")]
    return database.upsert_comments(str(db_path), records)


def import_csv(paths, db_path, platform: str = "tiktok", post_id: str = "") -> int:
    total = 0
    for path in paths:
        with open(path, newline="", encoding="utf-8-sig") as source:
            count = save_comments(csv.DictReader(source), db_path, platform, post_id)
        print(f"{path}: {count} rows")
        total += count
    return total


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Import TikTok comment CSVs into shared SQLite")
    parser.add_argument("csv_files", nargs="+")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--post-id", default="")
    args = parser.parse_args(argv)
    import_csv(args.csv_files, args.db, post_id=args.post_id)


if __name__ == "__main__":
    main()
