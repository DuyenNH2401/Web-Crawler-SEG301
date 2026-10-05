"""Điều phối CLI, quản lý tài nguyên và xử lý lỗi khi chạy chương trình."""
from __future__ import annotations

from contextlib import closing, nullcontext
import json
import logging
import sqlite3
from typing import Iterable
import uuid

from .clients import PublicReddit, api_client, session_client
from .config import LOG
from .crawler import crawl, import_jsonl, sync
from .database import Store, database_stats, show_comments
from .models import subreddit_name
from .network import diagnose_network
from .parser import parser
from .progress import CrawlProgress


def main(argv: Iterable[str] | None = None) -> int:
    args = parser().parse_args(argv)
    run_id = uuid.uuid4().hex[:12]
    logging.basicConfig(level=logging.INFO, format=f"%(levelname)s run={run_id} %(message)s", force=True)
    try:
        if hasattr(args, "subreddit"):
            args.subreddit = subreddit_name(args.subreddit)
        if args.command == "diagnose":
            output = diagnose_network()
        elif args.command == "show":
            shown = show_comments(args.db, limit=args.limit)
            LOG.info("finished command=show shown=%d", shown)
            return 0
        elif args.command == "stats":
            output = database_stats(args.db)
        else:
            dry_run = args.dry_run
            client = api_client() if args.command in {"crawl", "sync"} else None
            if args.command == "crawl-public":
                client = PublicReddit(user_agent=args.user_agent, request_delay=args.request_delay,
                                      timeout=args.timeout, comment_limit=args.max_comments)
                LOG.info("public JSON access: no credentials/cookies; stops on access errors")
            if args.command == "crawl-session":
                client = session_client(args.cookies_file, user_agent=args.user_agent,
                                        request_delay=args.request_delay, timeout=args.timeout,
                                        comment_limit=args.max_comments)
                LOG.info("session JSON access: local cookie file loaded; cookie values are not logged")
            try:
                # Copy existing data to memory so dry-run never writes even DDL or purge.
                monitor = (CrawlProgress(args.max_comments, dry_run=dry_run)
                           if args.command in {"crawl", "crawl-public", "crawl-session"} else nullcontext())
                with monitor as progress, Store(":memory:" if dry_run else args.db) as store:
                    if isinstance(client, PublicReddit):
                        client.progress = progress
                    if dry_run and args.db.exists():
                        with closing(sqlite3.connect(args.db.resolve().as_uri() + "?mode=ro", uri=True)) as source:
                            source.backup(store.conn)
                        store.ensure_schema()
                    purged = store.purge(retention_hours=args.retention_hours)
                    if args.command in {"crawl", "crawl-public", "crawl-session"}:
                        output = crawl(client, store, args.subreddit, max_comments=args.max_comments,
                                       max_posts=args.max_posts,
                                       more_limit=args.more_limit if args.command == "crawl" else 0,
                                       dry_run=dry_run, progress=progress)
                    elif args.command == "import":
                        output = import_jsonl(args.input, store, args.subreddit,
                                              max_comments=args.max_comments, dry_run=dry_run)
                    elif args.command == "sync":
                        output = sync(client, store, dry_run=dry_run)
                    else:
                        output = {}
                    output["would_purge" if dry_run else "purged"] = purged
                    output["dry_run"] = dry_run
            finally:
                if client is not None:
                    client.close()
        output["run_id"] = run_id
        print(json.dumps(output, ensure_ascii=False))
        LOG.info("finished command=%s", args.command)
        return 0
    except (ValueError, OSError, sqlite3.Error) as exc:
        LOG.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        LOG.warning("đã dừng; dữ liệu đã commit vẫn còn trong database")
        return 130
    except Exception as exc:
        # PRAW exceptions can contain request URLs or user content; show only type.
        LOG.error("API failed: %s; kiểm tra quyền truy cập/mạng. Dữ liệu đã lưu vẫn được giữ.",
                  type(exc).__name__)
        return 1
