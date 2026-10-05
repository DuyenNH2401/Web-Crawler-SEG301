"""
    pip install -r requirements.txt

    python main.py --url "https://www.youtube.com/watch?v=SGZkBoBsxsk"

    python main.py --input-file urls.txt

    python main.py --input-file urls.txt --max-comments 500 --no-replies --export data/exports/youtube.csv
"""

import argparse
import os
import sys
from datetime import datetime

import config
from crawler import YouTubeCommentCrawler
from database import Database
from youtube_parser import extract_video_id

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def parse_args():
    p = argparse.ArgumentParser(description="Cao comment YouTube theo schema chung cua nhom.")
    p.add_argument("--url", "-u", action="append", default=[],
                   help="Link video YouTube (dung nhieu lan duoc).")
    p.add_argument("--input-file", "-i",
                   help="File .txt, moi dong 1 link video.")
    p.add_argument("--max-comments", "-n", type=int, default=config.MAX_COMMENTS_PER_VIDEO,
                   help="So comment toi da moi video, tinh ca reply (0 = lay het).")
    p.add_argument("--sort", choices=["newest", "top"], default=config.DEFAULT_SORT,
                   help="Thu tu lay comment (newest day du hon).")
    p.add_argument("--no-replies", action="store_true",
                   help="Chi lay comment goc, bo reply.")
    p.add_argument("--min-words", type=int, default=config.MIN_WORDS,
                   help="Bo comment it hon N tu (0 = giu tat ca).")
    p.add_argument("--keywords-only", "-k", action="store_true", default=config.KEYWORDS_ONLY,
                   help="CHI luu comment chua it nhat 1 tu khoa (mac dinh: config.KEYWORDS).")
    p.add_argument("--keywords",
                   help='Danh sach tu khoa, cach nhau dau phay. Vd: "bắc,nam,bắc kỳ". '
                        "Truyen tham so nay = tu dong bat --keywords-only.")
    p.add_argument("--dedup-content", choices=["off", "author", "all", "global"], default=config.DEDUP_CONTENT,
                   help="Bo comment trung noi dung: off = giu het, author = cung nguoi + cung noi dung "
                        "(1 video), all = cung noi dung (1 video), global = cung noi dung (toan DB).")
    p.add_argument("--db", default=config.DB_PATH, help="Duong dan file SQLite.")
    p.add_argument("--export", "-o",
                   help="Sau khi cao, xuat TOAN BO database ra file .csv hoac .jsonl.")
    return p.parse_args()


def read_urls(args):
    urls = list(args.url)
    if args.input_file:
        with open(args.input_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.append(line)

    unique = {}
    for url in urls:
        key = extract_video_id(url) or url
        if key in unique:
            print(f"[DUP]  Bo qua link trung video {key}: {url}")
            continue
        unique[key] = url
    return list(unique.values())


def export(db, path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".jsonl":
        n = db.export_jsonl(path)
    else:
        n = db.export_csv(path)
    print(f"[EXPORT] {n} dong -> {path}")


def print_summary(stats, db):
    db_stats = db.get_stats()
    print()
    print("=" * 12 + " CRAWLING SUMMARY " + "=" * 12)
    print()
    print(f"Videos OK              : {stats['videos_ok']}")
    print(f"Videos Failed          : {stats['videos_failed']}")
    print(f"Comments Saved (root)  : {stats['comments_saved']}")
    print(f"Replies Saved          : {stats['replies_saved']}")
    print(f"Skipped (< min words)  : {stats['skipped_short']}")
    print(f"Skipped (no keyword)   : {stats['skipped_keyword']}")
    print(f"Duplicates Skipped     : {stats['duplicates']}")
    print(f"Duplicate Content      : {stats['duplicate_content']}")
    print(f"Already in DB          : {stats['already_in_db']}")
    print()
    print(f"Database Total         : {db_stats['total']} "
          f"({db_stats['roots']} goc / {db_stats['replies']} reply)")
    print("=" * 42)


def main():
    args = parse_args()
    urls = read_urls(args)
    if not urls:
        print("[!] Chua co link nao. Dung --url hoac --input-file. Xem: python main.py -h")
        sys.exit(1)

    keywords = None
    if args.keywords:
        keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    elif args.keywords_only:
        keywords = list(config.KEYWORDS)

    print("=" * 45)
    print("          YOUTUBE COMMENT CRAWLER")
    print("=" * 45)
    print()
    config.print_configuration(args.sort, not args.no_replies, args.max_comments,
                               args.min_words, keywords, args.dedup_content)

    db = Database(args.db)
    crawler = YouTubeCommentCrawler(db)
    try:
        for index, url in enumerate(urls, 1):
            print(f"({index}/{len(urls)}) {url}")
            crawler.crawl_video(
                url,
                max_comments=args.max_comments,
                sort=args.sort,
                include_replies=not args.no_replies,
                min_words=args.min_words,
                keywords=keywords,
                dedup_content=args.dedup_content,
            )
    except KeyboardInterrupt:
        print("\n[!] Da dung (Ctrl+C). Du lieu da cao van nam trong database.")

    print_summary(crawler.stats, db)
    if args.export:
        export(db, args.export)
    db.close()


if __name__ == "__main__":
    main()
