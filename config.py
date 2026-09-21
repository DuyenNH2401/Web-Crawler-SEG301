"""
Cau hinh cho Focused Web Crawler - SEG301 Assignment (Task 1)
Topic  : News & Information
Domain : BBC (bbc.com)

GHI CHU: doi tu NPR sang BBC vi:
1) BBC nam trong danh sach domain CHINH THUC cua de bai cho topic
   News & Information (BBC, CNN, The Guardian, Reuters), con NPR thi khong.
2) Khi test thuc te, NPR chan ket noi o tang TLS fingerprint
   (ConnectionResetError ngay khi bat tay HTTPS) - loi nay khong sua duoc
   chi bang requests + header, vuot qua gioi han cong nghe de bai cho phep.
   BBC thi da co nhieu tien le crawl thanh cong bang requests+BeautifulSoup
   thuan tuy.

LUU Y QUAN TRONG:
De bai yeu cau chon toi thieu 2 domain trong cung 1 topic
("You should select at least 2 domains from your chosen topic").
File nay dang cau hinh MAC DINH CHI VOI BBC de ban test truoc.
Truoc khi nop bai, hay them domain thu 2 (vi du CNN hoac The Guardian)
vao ca SEED_URLS va ALLOWED_DOMAINS ben duoi.
"""

import os

# ==========================================
# CRAWLER CONFIGURATION
# ==========================================
TOPIC = "News & Information"

# Seed URLs - diem bat dau crawl
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
REQUEST_TIMEOUT = 20  # tang len 20s vi route quoc te (VN -> server NPR o My) co the cham
CRAWL_DELAY = 1.5  # tu chon 1.5s de lich su, kiem tra lai Crawl-delay thuc te trong robots.txt cua domain ban chon

# User-Agent rieng, khong trung ten voi cac bot AI ma NPR chan dich danh
# (GPTBot, ClaudeBot, Google-Extended, Bytespider...) -> duoc coi la User-agent: *
USER_AGENT = "SEG301-EducationalCrawler/1.0 (student project; contact: hovinhhung29@gmail.com)"

# Header day du giong trinh duyet that. Chi co User-Agent thoi doi khi khien
# WAF/CDN cua mot so site (vd NPR) dua request vao hang cho thu thach bot,
# lam request bi treo den khi timeout thay vi tra loi/tu choi ngay.
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# Cac phan mo rong file KHONG phai trang HTML -> bo qua khi loc link (Task 5)
IGNORED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".css", ".js", ".zip", ".pdf", ".mp3", ".mp4", ".wav",
    ".woff", ".woff2", ".ttf", ".eot", ".xml", ".json",
}

# Scheme KHONG phai web -> bo qua (Task 5): mailto:, javascript:, tel:...
IGNORED_SCHEMES = {"mailto", "javascript", "tel", "ftp"}

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
    print("=" * 45)
    print()
