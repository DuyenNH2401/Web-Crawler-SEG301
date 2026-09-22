"""Run all five source crawlers and write one combined digest."""

import argparse
import os

import database
from config import DB_PATH, TOPIC
from crawler import CrawlerEngine
from digest import build_digest
from sources import ALL_SOURCES


<<<<<<< HEAD
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
=======
def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-source news crawler")
>>>>>>> 73c7225514e14883d3bf6cd6a00bb4611de504c1
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Override the configured page limit for every source",
    )
    parser.add_argument(
        "--articles-per-source",
        type=int,
        default=1,
        help="Number of article records to include from each source",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
        help="Override the source-specific maximum depth",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=None,
        help="Override the configured crawl delay for every source",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Override the source-specific request timeout",
    )
    parser.add_argument(
        "--reset-db",
        action="store_true",
        help="Delete the current crawl database before starting",
    )
    args = parser.parse_args()

    if args.reset_db and os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    engine = CrawlerEngine(db_path=DB_PATH)
    articles = []
    for source in ALL_SOURCES:
        print(f"\n===== {source.name} =====")
        articles.extend(
            engine.crawl(
                source,
                max_articles=args.articles_per_source,
                max_pages=args.max_pages,
                max_depth=args.max_depth,
                crawl_delay=args.delay,
                timeout=args.timeout,
            )
        )

    digest = build_digest(articles, topic=TOPIC)
    database.insert_digest(DB_PATH, digest)
    print(f"\nĐã lưu digest vào database: {DB_PATH} ({len(articles)} bài)")


if __name__ == "__main__":
    main()
