"""Run the cookie based Reddit crawler against the shared comments database."""

from __future__ import annotations

import json
from pathlib import Path
import sys

from shared_reddit import SharedRedditStore, show, stats


REDDIT_DIR = Path(__file__).resolve().parent / "reddit-crawler"


def main(argv: list[str], db_path: str) -> int:
    if str(REDDIT_DIR) not in sys.path:
        sys.path.insert(0, str(REDDIT_DIR))
    from reddit_app.client import RedditClient
    from reddit_app.crawler import crawl
    from reddit_app.main import build_parser

    args = build_parser().parse_args(argv)
    # The unified CLI accepts --db before the platform; the crawler parser also
    # accepts it after the subcommand for callers used to the standalone CLI.
    local_db = any(item == "--db" or item.startswith("--db=") for item in argv)
    path = Path(args.db if local_db else db_path)
    try:
        if args.command == "stats":
            result = stats(path)
        elif args.command == "show":
            show(path, limit=args.limit)
            return 0
        else:
            client = RedditClient(args.cookies_file, user_agent=args.user_agent,
                                  request_delay=args.request_delay, timeout=args.timeout)
            with SharedRedditStore(":memory:" if args.dry_run else path) as store:
                result = crawl(client, store, args.subreddit,
                               max_comments=args.max_comments, max_posts=args.max_posts,
                               dry_run=args.dry_run)
                result["dry_run"] = args.dry_run
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, OSError, RuntimeError) as error:
        print(f"Reddit: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Reddit: đã dừng; dữ liệu đã lưu vẫn còn trong database", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"Reddit: lỗi {type(error).__name__}; kiểm tra kết nối và quyền truy cập.",
              file=sys.stderr)
        return 1
