"""Command line entry point for collecting X replies into the shared schema."""

import argparse
import os
import sys

import database
from .export import export_comments
from .platforms.x import XCommentsCrawler, parse_post_id


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
DEFAULT_DB = os.path.join(ROOT_DIR, "data", "comments.db")
DEFAULT_PROFILE = os.path.join(ROOT_DIR, "data", "x_browser_profile")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect replies to X posts")
    parser.add_argument("--post", action="append", default=[],
                        help="X post URL or numeric ID; repeat for multiple posts")
    parser.add_argument("--posts-file", help="Text file with one post URL or ID per line")
    parser.add_argument("--mode", choices=("browser", "api"), default="browser",
                        help="Collection method (default: visible browser)")
    parser.add_argument("--profile-dir", default=DEFAULT_PROFILE,
                        help="Local browser profile with your X login")
    parser.add_argument("--cookie-file",
                        help="Optional local JSON file with auth_token and ct0 cookies")
    parser.add_argument("--browser-channel", choices=("chrome", "chromium"),
                        default="chrome", help="Browser to launch (default: installed Chrome)")
    parser.add_argument("--headless", action="store_true",
                        help="Run the selected browser without showing a window")
    parser.add_argument("--max-scrolls", type=int, default=30,
                        help="Maximum browser scroll steps per post (default: 30)")
    parser.add_argument("--archive", action="store_true",
                        help="Use full-archive search (requires X API access)")
    parser.add_argument("--max-comments", type=int, default=1000,
                        help="Maximum replies per post (default: 1000)")
    parser.add_argument("--db", default=DEFAULT_DB, help="SQLite database path")
    parser.add_argument("--output", help="Export path (default: data/x_comments.csv or .jsonl)")
    parser.add_argument("--format", choices=("csv", "jsonl"), default="csv")
    args = parser.parse_args(argv)

    posts = list(args.post)
    if args.posts_file:
        try:
            with open(args.posts_file, encoding="utf-8") as source:
                posts.extend(line.strip() for line in source
                             if line.strip() and not line.lstrip().startswith("#"))
        except OSError as error:
            parser.error(str(error))
    if not posts:
        parser.error("Supply --post or --posts-file")
    if args.max_comments < 1:
        parser.error("--max-comments must be at least 1")
    if args.max_scrolls < 1:
        parser.error("--max-scrolls must be at least 1")
    if args.archive and args.mode != "api":
        parser.error("--archive requires --mode api")
    post_inputs = {}
    try:
        for post in posts:
            post_inputs.setdefault(parse_post_id(post), post.strip())
    except ValueError as error:
        parser.error(str(error))
    post_ids = list(post_inputs)
    crawler = None
    try:
        if args.mode == "api":
            token = os.environ.get("X_BEARER_TOKEN", "")
            if not token:
                parser.error("Set the X_BEARER_TOKEN environment variable")
            crawler = XCommentsCrawler(token)
        else:
            from .platforms.x_browser import XBrowserCrawler
            crawler = XBrowserCrawler(args.profile_dir, cookie_file=args.cookie_file,
                                      headless=args.headless,
                                      browser_channel=args.browser_channel)
        for post_id in post_ids:
            if args.mode == "api":
                comments = crawler.crawl(post_id, archive=args.archive,
                                         max_comments=args.max_comments)
            else:
                comments = crawler.crawl(post_inputs[post_id], max_comments=args.max_comments,
                                         max_scrolls=args.max_scrolls)
            database.upsert_comments(args.db, comments)
            label = "visible posts" if args.mode == "browser" else "replies"
            print(f"Post {post_id}: collected {len(comments)} {label}")
    except Exception as error:
        print(f"Collection stopped: {error}", file=sys.stderr)
        return 1
    finally:
        if crawler is not None:
            crawler.close()

    output = args.output or os.path.join(ROOT_DIR, "data", f"x_comments.{args.format}")
    database.init_comments_db(args.db)
    rows = database.get_comments(args.db, "x", post_ids)
    export_comments(rows, output, args.format)
    print(f"Exported {len(rows)} comments to {output}")
    if args.mode == "browser":
        print("Browser mode may miss replies or include recommendations; review the export.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
