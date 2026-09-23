"""
Utility script to inspect and read crawled articles from crawler.db in the terminal.
Usage:
    python3 view_db.py              # Show summary and latest crawled articles
    python3 view_db.py --all        # Show all crawled pages
    python3 view_db.py --read 3     # Read the FULL article content of page with ID = 3
    python3 view_db.py --links      # Show sample extracted links
"""
import argparse
import os
import sqlite3
import sys
import textwrap

# Fix encoding on Windows terminal
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from config import DB_PATH

def inspect_db(show_all=False, show_links=False, read_id=None):
    if not os.path.exists(DB_PATH):
        print(f"[!] Database file not found at: {DB_PATH}")
        print("Please run `python3 main.py` first to crawl some pages.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Read specific article by ID
    if read_id is not None:
        cursor.execute("SELECT * FROM pages WHERE id = ?", (read_id,))
        row = cursor.fetchone()
        if not row:
            print(f"[!] No article found with ID = {read_id}")
            conn.close()
            return

        print("=" * 70)
        print(f"📖 BÀI BÁO CHI TIẾT [ID: {row['id']}]")
        print("=" * 70)
        print(f"📌 Tiêu đề     : {row['title']}")
        print(f"🌐 URL         : {row['url']}")
        print(f"🕒 Thời gian cào: {row['crawled_at']}")
        print(f"📶 Độ sâu (Depth): {row['depth']} | HTTP Status: {row['status_code']}")
        print(f"📊 Độ dài nội dung: {len(row['content'])} ký tự")
        print("-" * 70)
        print("📝 NỘI DUNG CHI TIẾT BÀI BÁO:")
        print("-" * 70)
        # Wrap paragraphs nicely
        for paragraph in row['content'].split("\n\n"):
            if paragraph.strip():
                print(textwrap.fill(paragraph.strip(), width=70))
                print()
        print("=" * 70)
        conn.close()
        return

    # 2. Database Overview
    cursor.execute("SELECT COUNT(*) FROM pages")
    page_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM links")
    link_count = cursor.fetchone()[0]

    print("=" * 70)
    print("📊 CRAWLER DATABASE OVERVIEW")
    print("=" * 70)
    print(f"File CSDL   : {DB_PATH}")
    print(f"Tổng số trang đã cào: {page_count}")
    print(f"Tổng số liên kết đã lưu: {link_count}")
    print("-" * 70)

    # 3. Show Pages
    limit_clause = "" if show_all else "LIMIT 6"
    cursor.execute(f"SELECT id, depth, status_code, title, url, length(content) as content_len FROM pages ORDER BY id ASC {limit_clause}")
    rows = cursor.fetchall()

    print(f"\n📑 DANH SÁCH BÀI BÁO ({'TẤT CẢ' if show_all else f'MẪU {len(rows)} TRANG ĐẦU'}):")
    print(f"{'ID':<4} | {'Depth':<5} | {'Code':<4} | {'Ký tự':<7} | {'Tiêu đề bài báo'}")
    print("-" * 70)
    for r in rows:
        print(f"{r['id']:<4} | {r['depth']:<5} | {r['status_code']:<4} | {r['content_len']:<7} | {r['title'][:48]}")
        print(f"     └─ URL: {r['url']}")
        print()

    print("💡 Mẹo: Chạy `python3 view_db.py --read <ID>` (ví dụ `python3 view_db.py --read 2`) để đọc TOÀN BỘ bài báo!")

    # 4. Show Links
    if show_links:
        cursor.execute("SELECT id, source_url, target_url FROM links LIMIT 10")
        links = cursor.fetchall()
        print(f"\n🔗 MẪU LIÊN KẾT ĐÃ BÓC TÁCH (10 LINK ĐẦU):")
        print(f"{'ID':<4} | {'Trang nguồn'} -> {'Trang đích'}")
        print("-" * 70)
        for l in links:
            print(f"[{l['id']}] {l['source_url'][:35]}... -> {l['target_url']}")

    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect crawler.db SQLite database")
    parser.add_argument("--all", action="store_true", help="Hiển thị tất cả bài báo trong CSDL")
    parser.add_argument("--links", action="store_true", help="Hiển thị mẫu các liên kết trích xuất")
    parser.add_argument("--read", type=int, default=None, help="Đọc toàn bộ nội dung bài báo theo ID")
    args = parser.parse_args()
    inspect_db(show_all=args.all, show_links=args.links, read_id=args.read)
