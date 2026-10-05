"""
Cào bình luận TikTok bằng Playwright.

Ý tưởng: mở trình duyệt thật (để TikTok tự ký request), "nghe lén" response
của API /api/comment/list/ rồi tự cuộn khung bình luận cho đến khi hết.

Cài đặt:
    pip install playwright
    playwright install chromium

Dùng:
    python tiktok_comments.py "https://www.tiktok.com/@user/video/1234567890"
    python tiktok_comments.py URL --max 500 --replies -o binh_luan.csv
"""
import argparse
import asyncio
import csv
from pathlib import Path
import random
import re
import sys
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from .comments_db import save_comments

ROOT_DIR = Path(__file__).resolve().parent.parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

COMMENT_API = "/api/comment/list/"
REPLY_API = "/api/comment/list/reply/"

# Giao diện TikTok hay đổi -> thử lần lượt các selector
COMMENT_ITEM_SELECTORS = [
    '[data-e2e="comment-level-1"]',
    'div[class*="DivCommentObjectWrapper"]',
    'div[class*="DivCommentItemWrapper"]',
]
OPEN_COMMENTS_SELECTORS = [
    '[data-e2e="comment-icon"]',
    'button[aria-label*="comment" i]',
]
CAPTCHA_SELECTOR = '#captcha-verify-container, div[class*="captcha" i]'
# Nút "View 3 replies" / "View 5 more" (locale ép về en-US)
VIEW_REPLIES_PATTERN = re.compile(r"^\s*View\s+\d+", re.I)

CSV_FIELDS = ["cid", "parent_cid", "post_id", "author_id", "username",
              "nickname", "text", "likes", "reply_count", "created_at"]


class Collector:
    def __init__(self, video_id):
        self.video_id = video_id
        self.rows = {}          # cid -> dict, tự loại trùng
        self.has_more = True

    def top_count(self):
        return sum(1 for r in self.rows.values() if not r["parent_cid"])

    def add(self, c, parent_id=""):
        cid = c.get("cid")
        if not cid or cid in self.rows:
            return
        user = c.get("user") or {}
        ts = c.get("create_time") or 0
        created = (datetime.fromtimestamp(ts, tz=timezone.utc)
                   .strftime("%Y-%m-%d %H:%M:%S") if ts else "")
        self.rows[cid] = {
            "cid": cid,
            "parent_cid": parent_id,
            "post_id": self.video_id,
            "author_id": user.get("uid", ""),
            "username": user.get("unique_id", ""),
            "nickname": user.get("nickname", ""),
            "text": c.get("text", ""),
            "likes": c.get("digg_count", 0),
            "reply_count": c.get("reply_comment_total", 0),
            "created_at": created,  # UTC, cùng định dạng CURRENT_TIMESTAMP
        }

    async def on_response(self, resp):
        url = resp.url
        # Kiểm tra REPLY_API trước vì nó cũng chứa chuỗi COMMENT_API
        if REPLY_API in url:
            kind = "reply"
        elif COMMENT_API in url:
            kind = "top"
        else:
            return

        qs = parse_qs(urlparse(url).query)
        vid = (qs.get("aweme_id") or qs.get("item_id") or [""])[0]
        if not self.video_id and vid and kind == "top":
            self.video_id = vid  # link rút gọn: lấy ID từ request đầu tiên
        if self.video_id and vid and vid != self.video_id:
            return  # response của video khác

        try:
            data = await resp.json()
        except Exception:
            return

        parent = qs.get("comment_id", [""])[0] if kind == "reply" else ""
        for c in data.get("comments") or []:
            self.add(c, parent)
        if kind == "top":
            self.has_more = bool(data.get("has_more"))


async def find_comment_items(page):
    for sel in COMMENT_ITEM_SELECTORS:
        items = page.locator(sel)
        if await items.count():
            return items
    return None


async def open_comment_panel(page):
    if await find_comment_items(page):
        return
    for sel in OPEN_COMMENTS_SELECTORS:
        btn = page.locator(sel).first
        if await btn.count():
            try:
                await btn.click(timeout=3000)
                await page.wait_for_timeout(2500)
                return
            except Exception:
                pass


async def wait_if_captcha(page):
    if await page.locator(CAPTCHA_SELECTOR).count():
        print("\n[!] Có captcha. Hãy tự giải trong cửa sổ trình duyệt...")
        while await page.locator(CAPTCHA_SELECTOR).count():
            await page.wait_for_timeout(2000)
        print("[+] Đã qua captcha, tiếp tục.")


async def scroll_comments(page):
    items = await find_comment_items(page)
    if items:
        last = items.nth(await items.count() - 1)
        try:
            await last.scroll_into_view_if_needed(timeout=3000)
            await last.hover(timeout=2000)
        except Exception:
            pass
    await page.mouse.wheel(0, 2000)


async def expand_replies(page):
    """Bấm các nút 'View N replies'. Trả về số nút đã bấm."""
    buttons = page.get_by_text(VIEW_REPLIES_PATTERN)
    clicked = 0
    for i in range(await buttons.count()):
        try:
            await buttons.nth(i).click(timeout=2000)
            clicked += 1
            await page.wait_for_timeout(random.randint(800, 1600))
        except Exception:
            pass
    return clicked


def save_csv(rows, path):
    # utf-8-sig để Excel hiển thị đúng tiếng Việt / emoji
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(rows)


async def run(url, out, max_comments, replies, headless, profile,
              channel=None, db=None):
    from playwright.async_api import async_playwright
    m = re.search(r"/video/(\d+)", url)
    col = Collector(m.group(1) if m else "")

    async with async_playwright() as p:
        # Persistent context: giữ cookie giữa các lần chạy, ít bị chặn hơn.
        # Bạn có thể tự đăng nhập một lần trong cửa sổ này nếu muốn.
        ctx = await p.chromium.launch_persistent_context(
            profile,
            channel=channel,  # "msedge"/"chrome": dùng trình duyệt có sẵn
            headless=headless,
            locale="en-US",
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        page.on("response", col.on_response)

        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)
        await wait_if_captcha(page)
        await open_comment_panel(page)

        # Cuộn đến khi hết bình luận / đủ số lượng / không còn gì mới
        stale = 0
        while col.has_more and col.top_count() < max_comments and stale < 8:
            before = len(col.rows)
            await scroll_comments(page)
            await page.wait_for_timeout(random.randint(1200, 2500))
            await wait_if_captcha(page)
            stale = stale + 1 if len(col.rows) == before else 0
            print(f"\rBình luận gốc: {col.top_count()}", end="", flush=True)
        print()

        if replies:
            print("Đang mở các trả lời...")
            for _ in range(20):
                if not await expand_replies(page):
                    break
                await wait_if_captcha(page)
            print(f"Tổng (gồm trả lời): {len(col.rows)}")

        await ctx.close()

    rows = list(col.rows.values())
    save_csv(rows, out)
    print(f"Đã lưu {len(rows)} dòng vào {out}")
    if db:
        n = save_comments(rows, db, platform="tiktok", post_id=col.video_id)
        print(f"Đã ghi {n} dòng vào SQLite: {db}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Cào bình luận TikTok")
    ap.add_argument("url", help="Link video TikTok")
    ap.add_argument("-o", "--out", default=str(ROOT_DIR / "data" / "tiktok_comments.csv"))
    ap.add_argument("--max", type=int, default=1000,
                    help="Số bình luận gốc tối đa (mặc định 1000)")
    ap.add_argument("--replies", action="store_true",
                    help="Lấy cả bình luận trả lời")
    ap.add_argument("--headless", action="store_true",
                    help="Ẩn trình duyệt (dễ bị chặn hơn)")
    ap.add_argument("--profile", default=str(ROOT_DIR / "tiktok_profile"),
                    help="Thư mục lưu cookie trình duyệt")
    ap.add_argument("--channel", choices=["msedge", "chrome"], default=None,
                    help="Dùng Edge/Chrome đã cài sẵn thay vì Chromium của Playwright")
    ap.add_argument("--db", default=str(ROOT_DIR / "data" / "comments.db"),
                    help="File SQLite chung")
    a = ap.parse_args(argv)
    asyncio.run(run(a.url, a.out, a.max, a.replies, a.headless, a.profile,
                    a.channel, a.db))


if __name__ == "__main__":
    main()
