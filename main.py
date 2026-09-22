"""Run all five source crawlers and write one combined digest."""

import argparse
import os

from config import DB_PATH, DIGEST_PATH, MAX_PAGES, TOPIC
from crawler import CrawlerEngine
from digest import build_digest, save_digest
from sources import ALL_SOURCES


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-source news crawler")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=MAX_PAGES,
        help="Maximum pages to inspect per source",
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
        default=0.5,
        help="Override the source-specific crawl delay",
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
    save_digest(digest, DIGEST_PATH)
    print(f"\nĐã tạo digest: {DIGEST_PATH}")
    print(digest.content)


if __name__ == "__main__":
    main()
