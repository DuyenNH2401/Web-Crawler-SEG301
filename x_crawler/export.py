"""Export collected X replies as CSV or JSONL."""

import csv
import json
import os
from typing import Mapping, Sequence


COMMENT_COLUMNS = (
    "id", "platform", "comment_id", "content", "author_id", "author_name",
    "parent_id", "post_id", "comment_url", "created_at", "like_count",
    "collected_at",
)


def export_comments(rows: Sequence[Mapping], path: str, format: str = "csv") -> None:
    if format not in ("csv", "jsonl"):
        raise ValueError("format must be csv or jsonl")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    encoding = "utf-8-sig" if format == "csv" else "utf-8"
    with open(path, "w", encoding=encoding, newline="") as output:
        if format == "csv":
            writer = csv.DictWriter(output, fieldnames=COMMENT_COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row[key] for key in COMMENT_COLUMNS})
        else:
            for row in rows:
                output.write(json.dumps(
                    {key: row[key] for key in COMMENT_COLUMNS}, ensure_ascii=False
                ) + "\n")
