"""
main.py - entry point.

Usage:
    python main.py
    python main.py --max-pages 20 --max-depth 1
"""

import argparse
import sys

import config
from crawler import Crawler

# Page titles contain characters (curly quotes, dashes, accents) that the
# default Windows console encoding cannot represent. Without this, printing a
# headline raises UnicodeEncodeError and kills the crawl mid-run.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def print_configuration():
    """Task 1 - show the crawling configuration."""
    print("=" * 41)
    print("          FOCUSED WEB CRAWLER")
    print("=" * 41)
    print("========== CRAWLER CONFIGURATION ==========")
    print(f"Topic          : {config.TOPIC}")
    print(f"Seed URLs      : {len(config.SEED_URLS)}")
    for i, url in enumerate(config.SEED_URLS, start=1):
        print(f"    {i}. {url}")
    print("Allowed Domains:")
    for domain in config.ALLOWED_DOMAINS:
        print(f"    - {domain}")
    print(f"Maximum Depth  : {config.MAX_DEPTH}")
    print(f"Maximum Pages  : {config.MAX_PAGES}")
    print(f"Request Timeout: {config.REQUEST_TIMEOUT} seconds")
    print(f"Crawl Delay    : {config.CRAWL_DELAY} second(s)")
    print(f"Respect robots : {config.RESPECT_ROBOTS}")
    print("=" * 43)


def parse_args():
    ap = argparse.ArgumentParser(description="SEG301 focused web crawler")
    ap.add_argument("--max-pages", type=int, help="override MAX_PAGES")
    ap.add_argument("--max-depth", type=int, help="override MAX_DEPTH")
    ap.add_argument("--delay", type=float, help="override CRAWL_DELAY")
    ap.add_argument("--links-per-page", type=int,
                    help="override MAX_LINKS_PER_PAGE (0 = unlimited)")
    ap.add_argument("--keep-db", action="store_true",
                    help="append to the existing database instead of clearing it")
    return ap.parse_args()


def main():
    args = parse_args()
    if args.max_pages is not None:
        config.MAX_PAGES = args.max_pages
    if args.max_depth is not None:
        config.MAX_DEPTH = args.max_depth
    if args.delay is not None:
        config.CRAWL_DELAY = args.delay
    if args.links_per_page is not None:
        config.MAX_LINKS_PER_PAGE = args.links_per_page

    print_configuration()

    crawler = Crawler(fresh=not args.keep_db)
    try:
        crawler.crawl()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user - showing partial results.")
        crawler.stats["finished_at"] = None
    finally:
        crawler.print_summary()
        crawler.close()


if __name__ == "__main__":
    sys.exit(main())
