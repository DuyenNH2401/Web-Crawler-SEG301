"""CLI điều phối các lệnh crawl, show, stats."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .client import RedditClient, USER_AGENT
from .crawler import crawl
from .database import DEFAULT_DB, Store, database_stats, show_comments


def build_parser() -> argparse.ArgumentParser:
    """Tạo cấu hình ArgumentParser cho các lệnh crawl, show, stats."""
    parser = argparse.ArgumentParser(description="Reddit comment crawler using cookie.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    crawl_p = subparsers.add_parser("crawl", help="Cào comment từ subreddit")
    crawl_p.add_argument("--cookies-file", required=True, type=Path, help="File chứa Cookie request header")
    crawl_p.add_argument("--subreddit", required=True, help="Tên subreddit (ví dụ: python hoặc r/python)")
    crawl_p.add_argument("--max-comments", required=True, type=int, help="Số comment tối đa cần cào")
    crawl_p.add_argument("--max-posts", type=int, default=100, help="Số bài viết mới tối đa cần duyệt")
    crawl_p.add_argument("--request-delay", type=float, default=2.0, help="Độ trễ giữa các request (giây)")
    crawl_p.add_argument("--timeout", type=float, default=30.0, help="Timeout socket (giây)")
    crawl_p.add_argument("--user-agent", default=USER_AGENT, help="User-Agent gửi tới Reddit")
    crawl_p.add_argument("--db", type=Path, default=DEFAULT_DB, help="File database SQLite")
    crawl_p.add_argument("--dry-run", action="store_true", help="Chạy thử không ghi database")

    show_p = subparsers.add_parser("show", help="Xem nội dung comment đã lưu")
    show_p.add_argument("--limit", type=int, default=10, help="Số comment muốn xem")
    show_p.add_argument("--db", type=Path, default=DEFAULT_DB, help="File database SQLite")

    stats_p = subparsers.add_parser("stats", help="Thống kê số lượng comment")
    stats_p.add_argument("--db", type=Path, default=DEFAULT_DB, help="File database SQLite")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "show":
            show_comments(args.db, limit=args.limit)
            return 0
        if args.command == "stats":
            print(json.dumps(database_stats(args.db), ensure_ascii=False))
            return 0
        if args.command == "crawl":
            client = RedditClient(args.cookies_file, user_agent=args.user_agent,
                                  request_delay=args.request_delay, timeout=args.timeout)
            db_path = ":memory:" if args.dry_run else args.db
            with Store(db_path) as store:
                res = crawl(client, store, args.subreddit, max_comments=args.max_comments,
                            max_posts=args.max_posts, dry_run=args.dry_run)
                res["dry_run"] = args.dry_run
                print(json.dumps(res, ensure_ascii=False))
                return 0
    except Exception as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
