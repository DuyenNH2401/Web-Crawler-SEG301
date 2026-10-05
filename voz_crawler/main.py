"""Nhận tham số dòng lệnh và chạy crawler VOZ."""

import argparse
import math
from pathlib import Path
import sys

import requests

from .config import (DEFAULT_CSV, DEFAULT_DB, DEFAULT_DELAY,
                     DEFAULT_FORUM_PAGES, DEFAULT_MAX_THREADS, DEFAULT_THREAD_PAGES)
from .crawler import crawl


def main(argv: list[str] | None = None) -> int:
    # PowerShell trên Windows có thể dùng mã hóa console không hỗ trợ tiếng Việt.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Cào bình luận công khai trong box Chuyện trò linh tinh của VOZ")
    parser.add_argument("--forum-pages", type=int, default=DEFAULT_FORUM_PAGES,
                        help=f"Số trang danh sách chủ đề (mặc định: {DEFAULT_FORUM_PAGES})")
    parser.add_argument("--max-threads", type=int, default=DEFAULT_MAX_THREADS,
                        help=f"Số chủ đề tối đa (mặc định: {DEFAULT_MAX_THREADS})")
    parser.add_argument("--thread-pages", type=int, default=DEFAULT_THREAD_PAGES,
                        help=f"Số trang mỗi chủ đề (mặc định: {DEFAULT_THREAD_PAGES})")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                        help=f"Nghỉ giữa các yêu cầu, giây (mặc định: {DEFAULT_DELAY})")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="File SQLite chung")
    parser.add_argument("--output", type=Path, default=DEFAULT_CSV, help="File CSV xuất ra")
    args = parser.parse_args(argv)
    if (args.forum_pages < 1 or args.max_threads < 1 or args.thread_pages < 1
            or not math.isfinite(args.delay) or args.delay < 0):
        parser.error("Số trang và số chủ đề phải >= 1; delay phải hữu hạn và >= 0")
    try:
        crawl(args.forum_pages, args.max_threads, args.thread_pages,
              args.delay, args.db, args.output)
    except (requests.RequestException, RuntimeError, OSError) as error:
        parser.exit(1, f"Không thể cào VOZ: {error}\n")
    return 0
