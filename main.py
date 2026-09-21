import argparse
import sys
from config import (
    TOPIC,
    SEED_URLS,
    ALLOWED_DOMAINS,
    MAX_DEPTH,
    MAX_PAGES,
    REQUEST_TIMEOUT,
    CRAWL_DELAY,
    DB_PATH,
)
from crawler import FocusedCrawler
import database


def print_banner(
    topic: str,
    seeds: list,
    allowed_domains: list,
    max_pages: int,
    max_depth: int,
    timeout: int,
    delay: float,
) -> None:
    """Display the crawler configuration banner as required by Task 1."""
    print("=========================================")
    print("FOCUSED WEB CRAWLER")
    print("=========================================")
    print(f"Topic: {topic}")
    print("Seed URLs:")
    for idx, url in enumerate(seeds, start=1):
        print(f"{idx}. {url}")
    print("Allowed Domains:")
    for domain in allowed_domains:
        print(f"- {domain}")
    print(f"Maximum Pages : {max_pages}")
    print(f"Maximum Depth : {max_depth}")
    print(f"Request Timeout: {timeout} seconds")
    print(f"Crawl Delay   : {delay} second(s)")
    print("-----------------------------------------")


def print_summary(
    topic: str, seeds_count: int, crawler: FocusedCrawler, db_path: str
) -> None:
    """
    Display the crawling summary statistics computed from database and crawler state.
    Task 14: Crawling Statistics.
    """
    stats = database.get_summary_stats(db_path)

    print("\n========== CRAWLING SUMMARY ==========")
    print(f"Topic                  : {topic}")
    print(f"Seed URLs              : {seeds_count}")
    print(f"Pages Crawled (run)    : {crawler.pages_crawled}")
    print(f"Pages Stored (database): {stats['pages_crawled']}")
    print(f"Unique URLs Discovered : {crawler.frontier.total_discovered}")
    print(
        f"Skipped URLs           : {crawler.frontier.total_skipped + crawler.skipped_robots}"
    )
    print(f"Failed Requests        : {crawler.failed_requests}")
    print(f"Maximum Depth          : {crawler.max_depth}\n")

    print("\nStored database breakdown:")

    # Depth breakdown (the database can include rows from earlier runs)
    for depth in range(crawler.max_depth + 1):
        count = stats["depth_counts"].get(depth, 0)
        print(f"Depth {depth:<16} : {count} pages")
    print()

    # HTTP status code breakdown
    for code, count in sorted(stats["status_code_counts"].items()):
        print(f"HTTP {code:<17} : {count}")

    print("=======================================")


def main():
    parser = argparse.ArgumentParser(description="Focused Web Crawler for SEG301")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=MAX_PAGES,
        help="Maximum number of pages to crawl",
    )
    parser.add_argument(
        "--max-depth", type=int, default=MAX_DEPTH, help="Maximum crawl depth"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=CRAWL_DELAY,
        help="Crawl delay between requests in seconds",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=REQUEST_TIMEOUT,
        help="HTTP request timeout in seconds",
    )
    parser.add_argument(
        "--reset-db",
        action="store_true",
        help="Delete existing database before crawling",
    )

    args = parser.parse_args()

    if args.reset_db:
        import os

        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
            print(f"Cleared existing database at {DB_PATH}")

    print_banner(
        topic=TOPIC,
        seeds=SEED_URLS,
        allowed_domains=ALLOWED_DOMAINS,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        timeout=args.timeout,
        delay=args.delay,
    )

    crawler = FocusedCrawler(
        seed_urls=SEED_URLS,
        allowed_domains=ALLOWED_DOMAINS,
        max_depth=args.max_depth,
        max_pages=args.max_pages,
        crawl_delay=args.delay,
        timeout=args.timeout,
        db_path=DB_PATH,
    )

    try:
        crawler.start()
    except KeyboardInterrupt:
        print(
            "\n[!] Crawling interrupted by user. Generating summary from collected data..."
        )

    print_summary(
        topic=TOPIC, seeds_count=len(SEED_URLS), crawler=crawler, db_path=DB_PATH
    )


if __name__ == "__main__":
    main()
