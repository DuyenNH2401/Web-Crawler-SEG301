"""
Xem nhanh / xuat du lieu trong data/comments.db.

    python view_db.py                        # tong quan + 10 comment moi nhat
    python view_db.py --post SGZkBoBsxsk     # comment cua 1 video
    python view_db.py --search "bắc kỳ"      # tim comment chua chuoi
    python view_db.py --export data/exports/youtube.csv
    python view_db.py --export out.jsonl --post SGZkBoBsxsk
"""

import argparse
import os
import sys
import textwrap

import config
from database import Database

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def show_rows(rows):
    for r in rows:
        tag = "↳ reply" if r["parent_id"] != config.ROOT else "● goc"
        print(f"[{r['id']}] {tag} | {r['author_name']} | {r['created_at']} | 👍 {r['like_count']}")
        print(textwrap.indent(textwrap.fill(r["content"], 90), "    "))
        print(f"    {r['comment_url']}")
        print()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=config.DB_PATH)
    p.add_argument("--post", help="Chi xem/xuat 1 post_id (video id).")
    p.add_argument("--search", help="Tim comment chua chuoi nay (khong phan biet hoa thuong).")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--export", help="Xuat ra .csv hoac .jsonl (dung schema).")
    args = p.parse_args()

    if not os.path.exists(args.db):
        print(f"[!] Chua co database: {args.db}. Chay `python main.py --url ...` truoc.")
        return

    db = Database(args.db)

    if args.export:
        if args.export.lower().endswith(".jsonl"):
            n = db.export_jsonl(args.export, args.post)
        else:
            n = db.export_csv(args.export, args.post)
        print(f"[EXPORT] {n} dong -> {args.export}")
        db.close()
        return

    stats = db.get_stats()
    print("=" * 60)
    print(f"Tong comment : {stats['total']} ({stats['roots']} goc / {stats['replies']} reply)")
    print(f"author UNKNOWN: {stats['unknown_author']}")
    print("-" * 60)
    for row in stats["per_post"]:
        print(f"{row['platform']:8} {row['post_id']:15} {row['n']:6} comment | cao luc {row['last']}")
    print("=" * 60)
    print()

    sql = "SELECT * FROM comments WHERE 1=1"
    params = []
    if args.post:
        sql += " AND post_id = ?"
        params.append(args.post)
    if args.search:
        # LIKE cua SQLite khong lower() duoc tieng Viet co dau -> loc bang Python
        rows = [r for r in db.conn.execute(sql + " ORDER BY id DESC", params)
                if args.search.lower() in r["content"].lower()][: args.limit]
    else:
        rows = db.conn.execute(sql + " ORDER BY id DESC LIMIT ?", params + [args.limit]).fetchall()
    show_rows(rows)
    db.close()


if __name__ == "__main__":
    main()
