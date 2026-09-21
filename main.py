"""
Entry point - Focused Web Crawler (SEG301 Assignment, Task 9)

CACH CHAY:
    pip install -r requirements.txt
    python main.py
"""

import config
from crawler import Crawler


def print_summary(stats, db):
    db_stats = db.get_stats()

    print()
    print("=" * 12 + " CRAWLING SUMMARY " + "=" * 12)
    print()
    print(f"Topic                  : {config.TOPIC}")
    print()
    print(f"Seed URLs              : {len(config.SEED_URLS)}")
    print(f"Pages Crawled          : {stats['pages_crawled']}")
    print(f"Unique URLs Discovered : {stats['unique_urls_discovered']}")
    print(f"Skipped URLs           : {stats['skipped_urls']}")
    print(f"Failed Requests        : {stats['failed_requests']}")
    print()
    print(f"Maximum Depth          : {config.MAX_DEPTH}")
    print()
    for depth in sorted(db_stats["depth_counts"]):
        print(f"Depth {depth}                : {db_stats['depth_counts'][depth]} pages")
    print()
    for code in sorted(db_stats["status_counts"]):
        print(f"HTTP {code}               : {db_stats['status_counts'][code]}")
    print()
    print("=" * 43)


def main():
    print("=" * 43)
    print("          FOCUSED WEB CRAWLER")
    print("=" * 43)
    print()

    config.print_configuration()

    crawler = Crawler()
    try:
        stats = crawler.crawl(config.SEED_URLS, config.MAX_PAGES)
    except KeyboardInterrupt:
        print("\n[!] Da dung crawl (Ctrl+C). Dang xuat thong ke tu du lieu da thu thap...")
        stats = crawler.stats

    print_summary(stats, crawler.db)
    crawler.db.close()


if __name__ == "__main__":
    main()
