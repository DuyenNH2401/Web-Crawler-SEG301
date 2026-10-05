"""Lưu bình luận vào database chung và xuất CSV để xem nhanh."""

import csv
from pathlib import Path

from database import upsert_comments
from models import Comment

from .config import CSV_FIELDS
from .models import Thread


def save_comments(db_path: Path, comments: list[Comment]) -> None:
    upsert_comments(str(db_path), comments)


def write_csv(csv_path: Path, rows: list[tuple[Thread, Comment]]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for thread, comment in rows:
            writer.writerow({
                "post_id": thread.thread_id, "thread_title": thread.title,
                "comment_id": comment.comment_id, "author_name": comment.author_name,
                "content": comment.content, "created_at": comment.created_at,
                "comment_url": comment.comment_url,
            })
