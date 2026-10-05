"""Khai báo lệnh CLI và kiểm tra các tham số số học."""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from .config import (
    DEFAULT_DB, DEFAULT_MAX_POSTS, DEFAULT_MORE_LIMIT, DEFAULT_REQUEST_DELAY,
    DEFAULT_RETENTION_HOURS, DEFAULT_SHOW_LIMIT, DEFAULT_TIMEOUT,
    PUBLIC_USER_AGENT, SESSION_USER_AGENT,
)


def positive_int(value: str) -> int:
    try:
        number = int(value)
        if number <= 0:
            raise ValueError
        return number
    except ValueError:
        raise argparse.ArgumentTypeError("giá trị phải là số nguyên > 0") from None


def nonnegative_int(value: str) -> int:
    try:
        number = int(value)
        if number < 0:
            raise ValueError
        return number
    except ValueError:
        raise argparse.ArgumentTypeError("giá trị phải là số nguyên >= 0") from None


def positive_float(value: str) -> float:
    try:
        number = float(value)
        if not math.isfinite(number) or number <= 0:
            raise ValueError
        return number
    except ValueError:
        raise argparse.ArgumentTypeError("giá trị phải là số hữu hạn > 0") from None


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Lấy comment subreddit / nhập JSONL vào SQLite.")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("diagnose", help="Kiểm tra DNS và hostname proxy, không đọc/ghi database")
    for name, description in (("crawl", "Lấy từ API được cấp quyền"),
                              ("crawl-public", "Thử đọc JSON công khai, không gửi credentials/cookie"),
                              ("crawl-session", "Đọc JSON Reddit với cookie từ file local"),
                              ("import", "Nhập JSONL (offline)"),
                              ("sync", "Cập nhật/xoá comment đã lưu từ API"),
                              ("purge", "Xoá dữ liệu quá hạn"),
                              ("stats", "Thống kê database"),
                              ("show", "Xem nội dung comment, mỗi comment một dòng")):
        sub = commands.add_parser(name, help=description)
        sub.add_argument("--db", type=Path, default=DEFAULT_DB)
        if name != "show":
            sub.add_argument("--retention-hours", type=positive_float, default=DEFAULT_RETENTION_HOURS,
                             help="Thời gian giữ dữ liệu kể từ lần lưu đầu; mặc định 48 giờ")
        if name in {"crawl", "crawl-public", "crawl-session", "import", "sync", "purge"}:
            sub.add_argument("--dry-run", action="store_true", help="Không thay đổi database")
        if name in {"crawl", "crawl-public", "crawl-session", "import"}:
            sub.add_argument("--subreddit", required=True)
            sub.add_argument("--max-comments", required=True, type=positive_int,
                             help="Tổng số comment hợp lệ, duy nhất tối đa trong lần chạy")
        if name in {"crawl", "crawl-public", "crawl-session"}:
            sub.add_argument("--max-posts", type=positive_int, default=DEFAULT_MAX_POSTS)
        if name == "crawl":
            sub.add_argument("--more-limit", type=nonnegative_int, default=DEFAULT_MORE_LIMIT,
                             help="Số nhánh load-more tối đa mở mỗi bài; 0: không mở thêm")
        if name in {"crawl-public", "crawl-session"}:
            sub.add_argument("--request-delay", type=positive_float, default=DEFAULT_REQUEST_DELAY,
                             help="Khoảng cách tối thiểu giữa request, mặc định 2 giây")
            sub.add_argument("--timeout", type=positive_float, default=DEFAULT_TIMEOUT)
            sub.add_argument("--user-agent", default=PUBLIC_USER_AGENT if name == "crawl-public"
                             else SESSION_USER_AGENT,
                             help="Mô tả crawler trung thực; có thể thêm tên tài khoản liên hệ")
        if name == "crawl-session":
            sub.add_argument("--cookies-file", required=True, type=Path,
                             help="File local chứa Cookie request header; không truyền giá trị cookie qua args/chat")
        if name == "import":
            sub.add_argument("--input", type=Path, required=True)
        if name == "show":
            sub.add_argument("--limit", type=positive_int, default=DEFAULT_SHOW_LIMIT,
                             help="Số comment tối đa hiển thị; mặc định 10, thu thập gần nhất trước")
    return root
