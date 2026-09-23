"""
Cau hinh cho Focused Web Crawler - SEG301 Assignment (Task 1)
Topic  : News & Information
Domain : Global Times (globaltimes.cn)

GHI CHU LICH SU CHON DOMAIN: NPR -> BBC -> Global Times.
- NPR bi loai vi chan ket noi o tang TLS fingerprint (ConnectionResetError
  ngay khi bat tay HTTPS) - loi nay khong sua duoc chi bang requests +
  header, vuot qua gioi han cong nghe de bai cho phep.
- BBC dung de test tam trong luc cho ca nhom thong nhat phan cong domain.
- Global Times la domain chinh thuc duoc phan cong cho phan viec nay
  (moi thanh vien trong nhom phu trach 1 domain rieng: BBC, CNN,
  VnExpress, The Guardian, Global Times - gop lai du 2+ domain cho ca
  nhom theo dung yeu cau de bai: "You should select at least 2 domains
  from your chosen topic").
"""

import os

# ==========================================
# CRAWLER CONFIGURATION
# ==========================================
TOPIC = "News & Information"

# Seed URL - diem bat dau crawl. Dung trang chu vi topic khong gioi han
# rieng 1 muc nao trong site (khac ban truoc day co gioi han rieng muc CHINA).
SEED_URLS = [
    "https://www.globaltimes.cn/",
]

# Domain duoc phep crawl (khong phan biet co/khong co tien to "www.",
# xem ham normalize_domain() trong parser.py)
ALLOWED_DOMAINS = [
    "globaltimes.cn",
]

# Gioi han crawl
MAX_DEPTH = 3
MAX_PAGES = 100
REQUEST_TIMEOUT = 20  # tang len 20s vi route quoc te co the cham hon binh thuong
CRAWL_DELAY = 1.5  # tu chon 1.5s de lich su, kiem tra lai Crawl-delay thuc te trong robots.txt cua domain

# User-Agent rieng, khong trung ten voi cac bot AI hay bi mot so site
# chan dich danh (GPTBot, ClaudeBot, Google-Extended, Bytespider...)
USER_AGENT = "SEG301-EducationalCrawler/1.0 (student project; contact: hovinhhung29@gmail.com)"

# Header day du giong trinh duyet that. Chi co User-Agent thoi doi khi khien
# WAF/CDN cua mot so site dua request vao hang cho thu thach bot, lam
# request bi treo den khi timeout thay vi tra loi/tu choi ngay.
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# ==========================================
# LOC O NGOAI (URL-LEVEL FILTERING)
# Loc TRUOC khi tai trang / truoc khi them URL vao Frontier - Task 5
# ==========================================

# Cac phan mo rong file KHONG phai trang HTML -> bo qua khi loc link
IGNORED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".css", ".js", ".zip", ".pdf", ".mp3", ".mp4", ".wav",
    ".woff", ".woff2", ".ttf", ".eot", ".xml", ".json",
}

# Scheme KHONG phai web -> bo qua: mailto:, javascript:, tel:, ftp:
IGNORED_SCHEMES = {"mailto", "javascript", "tel", "ftp"}

# ==========================================
# LOC BEN TRONG (CONTENT-LEVEL FILTERING)
# Loc SAU khi da tai trang ve va parse HTML, truoc khi luu vao database
# ==========================================

# Cac selector CUA KHOI CHUA BAI VIET THAT SU. Thu tung selector theo
# THU TU, dung ket qua khop DAU TIEN tim thay tren trang.
# ".article_content" la class THAT cua globaltimes.cn, da xac nhan bang
# DevTools (F12 -> chuot phai vao doan van bai viet -> Inspect ->
# div.article_page > div.article > div.article_content).
ARTICLE_CONTENT_SELECTORS = [
    ".article_content",
    "article",
    "#Content",
]

# Neu True: trang KHONG khop bat ky selector nao o tren (vd trang danh
# muc/trang chu, khong phai bai viet) se bi bo qua, KHONG luu vao pages
# - chi dung de tiep tuc trich link cho BFS di tiep sang trang khac.
REQUIRE_ARTICLE_MATCH = True

# Cac selector CAN XOA truoc khi trich text (menu dieu huong, banner,
# quang cao, box "bai viet lien quan", nut share...) - ap dung cho ca
# truong hop khop ARTICLE_CONTENT_SELECTORS lan truong hop fallback.
EXCLUDE_SELECTORS = [
    "nav", "header", "footer", "script", "style", "noscript", "form", "iframe",
    ".related", ".related-articles", ".related-box", ".recommend",
    ".share", ".share-buttons", ".social-share",
    ".ad", ".ads", ".advertisement", ".breadcrumb",
]

# Sau khi loc xong, neu content con lai qua ngan (vd trich nham 1 khoi
# gan nhu rong) thi bo qua, khong luu. Bai viet that thuong dai hon
# nguong nay rat nhieu.
MIN_CONTENT_LENGTH = 500

# Duong dan luu database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "crawler.db")


def print_configuration():
    """In cau hinh crawl (Task 1 - Output)."""
    print("=" * 11 + " CRAWLER CONFIGURATION " + "=" * 11)
    print()
    print(f"Topic           : {TOPIC}")
    print(f"Seed URLs       : {len(SEED_URLS)}")
    print("Allowed Domains :")
    for d in ALLOWED_DOMAINS:
        print(f"    - {d}")
    print()
    print(f"Maximum Depth   : {MAX_DEPTH}")
    print(f"Maximum Pages   : {MAX_PAGES}")
    print(f"Request Timeout : {REQUEST_TIMEOUT} seconds")
    print(f"Crawl Delay     : {CRAWL_DELAY} second(s)")
    print()
    print(f"Require Article Match : {REQUIRE_ARTICLE_MATCH}")
    print(f"Min Content Length    : {MIN_CONTENT_LENGTH} characters")
    print("=" * 45)
    print()
