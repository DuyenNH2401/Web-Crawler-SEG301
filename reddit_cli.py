"""Run the existing Reddit crawler against the shared database."""

from __future__ import annotations

from contextlib import nullcontext
import json
from pathlib import Path
import sys

from shared_reddit import SharedRedditStore, show, stats


REDDIT_DIR = Path(__file__).resolve().parent / "seg301_crawler_reddit"


def main(argv: list[str], db_path: str) -> int:
    if str(REDDIT_DIR) not in sys.path:
        sys.path.insert(0, str(REDDIT_DIR))
    from reddit_app.clients import PublicReddit, api_client, session_client
    from reddit_app.crawler import crawl, import_jsonl, sync
    from reddit_app.models import subreddit_name
    from reddit_app.network import diagnose_network
    from reddit_app.parser import parser
    from reddit_app.progress import CrawlProgress

    args = parser().parse_args(argv)
    path = Path(db_path)
    try:
        if args.command == "diagnose":
            result = diagnose_network()
        elif args.command == "stats":
            result = stats(path)
        elif args.command == "show":
            show(path, limit=args.limit)
            return 0
        else:
            client = None
            if args.command in {"crawl", "sync"}:
                client = api_client()
            elif args.command == "crawl-public":
                client = PublicReddit(user_agent=args.user_agent, request_delay=args.request_delay,
                                      timeout=args.timeout, comment_limit=args.max_comments)
            elif args.command == "crawl-session":
                client = session_client(args.cookies_file, user_agent=args.user_agent,
                                        request_delay=args.request_delay, timeout=args.timeout,
                                        comment_limit=args.max_comments)
            try:
                dry_run = args.dry_run
                monitor = (CrawlProgress(args.max_comments, dry_run=dry_run)
                           if args.command in {"crawl", "crawl-public", "crawl-session"}
                           else nullcontext())
                with monitor as progress, SharedRedditStore(":memory:" if dry_run else path) as store:
                    if dry_run and path.exists():
                        import sqlite3
                        with sqlite3.connect(path) as source:
                            source.backup(store.conn)
                        store.ensure_schema()
                    if isinstance(client, PublicReddit):
                        client.progress = progress
                    if args.command in {"crawl", "crawl-public", "crawl-session"}:
                        result = crawl(client, store, subreddit_name(args.subreddit),
                                       max_comments=args.max_comments, max_posts=args.max_posts,
                                       more_limit=args.more_limit if args.command == "crawl" else 0,
                                       dry_run=dry_run, progress=progress)
                    elif args.command == "import":
                        result = import_jsonl(args.input, store, args.subreddit,
                                              max_comments=args.max_comments, dry_run=dry_run)
                    elif args.command == "sync":
                        result = sync(client, store, dry_run=dry_run)
                    elif args.command == "purge":
                        result = {"would_purge" if dry_run else "purged":
                                  store.purge(retention_hours=args.retention_hours)}
                    result["dry_run"] = dry_run
            finally:
                if client is not None:
                    client.close()
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, OSError, RuntimeError) as error:
        print(f"Reddit: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Reddit: đã dừng; dữ liệu đã lưu vẫn còn trong database", file=sys.stderr)
        return 130
    except Exception as error:
        # Third-party errors may contain request URLs or credentials in their message.
        print(f"Reddit: lỗi {type(error).__name__}; kiểm tra kết nối và quyền truy cập.",
              file=sys.stderr)
        return 1
