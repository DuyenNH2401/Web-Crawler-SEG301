# Focused Web Crawler - SEG301 Assignment

Crawler tap trung (focused web crawler) viet bang Python, dung `requests` +
`BeautifulSoup` de crawl trang, va SQLite de luu du lieu. Crawl theo thu tu
BFS (Breadth-First Search) qua URL Frontier.

## 1. Selected Topic and Domain

- **Topic:** News & Information
- **Domain (phu trach ca nhan):** Global Times — `globaltimes.cn`

**Lich su chon domain:** ban dau du dinh crawl NPR, nhung khi test thuc te
NPR chan ket noi ngay o tang TLS handshake (`ConnectionResetError` xay ra
truoc khi kip nhan response) - day la kieu chan dua tren "TLS fingerprint"
cua client, khong sua duoc chi bang `requests` + header thong thuong (nam
ngoai kha nang cua cong nghe de bai cho phep). Sau do doi tam sang BBC de
test trong luc nhom thong nhat phan cong, va cuoi cung nhan Global Times
lam domain chinh thuc phu trach (nhom gom 5 thanh vien, moi nguoi 1 domain:
BBC, CNN, VnExpress, The Guardian, Global Times — gop du 2+ domain cho ca
nhom theo dung yeu cau de bai).

Crawler nay dung `urllib.robotparser` de tu dong kiem tra `robots.txt` cua
domain truoc moi request (khong hardcode luat), nen se tu dong bo qua bat
ky duong dan nao bi cam. Truoc khi crawl, nen tu kiem tra nhanh bang trinh
duyet tai `https://www.globaltimes.cn/robots.txt` de biet truoc cac gioi han.

## 2. Seed URLs

```
https://www.globaltimes.cn/
```

Dung thang trang chu (khong gioi han rieng 1 muc/section nao) vi topic
duoc giao la "News & Information" noi chung, khong yeu cau rieng 1 chu de
con nao trong site.

## 3. Crawling Configuration

Cau hinh tap trung trong [`config.py`](config.py):

| Parameter | Value |
| :--- | :--- |
| Maximum Depth | 3 |
| Maximum Pages | 100 |
| Request Timeout | 20 giay |
| Crawl Delay | 1.5 giay |
| Require Article Match | True |
| Min Content Length | 500 ky tu |

Ly do chon Crawl Delay 1.5s: de dam bao lich su, tranh gui request qua
nhanh gay tai cho server va giam nguy co bi chan boi cac lop chong bot -
nen kiem tra lai `Crawl-delay` thuc te trong `robots.txt` cua domain va
dieu chinh neu can. Request Timeout duoc dat 20s (thay vi 10s mac dinh)
vi route mang quoc te co the co do tre cao hon binh thuong.

## 4. Crawling Strategy

URL Frontier (`url_frontier.py`) dung `collections.deque` de dam bao thu
tu BFS: cac trang o depth thap hon luon duoc crawl truoc cac trang o depth
cao hon. Frontier dong thoi giu 1 `set` cac URL dang cho (`_queued_set`) va
1 `set` cac URL da crawl (`visited`) de khong bao gio them 2 lan cung 1 URL
vao hang doi, va khong crawl lai URL da xu ly (Task 7 - tranh duplicate).

Vong lap chinh dung khi **mot trong hai dieu kien** xay ra truoc: so trang
da crawl thanh cong dat `MAX_PAGES`, hoac Frontier rong (khong con URL nao
de crawl).

Crawler loc du lieu qua **2 tang doc lap**: loc o ngoai (truoc khi tai
trang) va loc ben trong (sau khi da tai trang ve). Ly do tach lam 2 tang
thay vi chi loc 1 lan: loc o ngoai giup tranh gui request thua (tiet kiem
thoi gian, giam tai server, tranh bi chan vi request qua nhieu), con loc
ben trong moi biet duoc trang do co that su la bai viet tin tuc hay chi la
trang danh muc/trang dieu huong (thu duoc biet duoc sau khi da co HTML).

## 5. URL Filtering Rules (Loc o ngoai — truoc khi tai trang)

Trong `parser.py`, moi link trich xuat tu the `<a href>` phai vuot qua het
cac buoc loc sau moi duoc them vao Frontier:

1. Bo qua scheme khong phai web: `mailto:`, `javascript:`, `tel:`, `ftp:`
   (`extract_links()`, kiem tra `config.IGNORED_SCHEMES`)
2. Chuyen URL tuong doi thanh URL tuyet doi bang `urljoin(current_url, href)`
3. Chuan hoa URL: bo fragment (`#...`), bo dau `/` thua o cuoi path
   (`normalize_url()`)
4. Bo qua file khong phai HTML dua tren duoi file: `.jpg, .png, .css, .js,
   .pdf, .zip, .mp3, .mp4, .woff, .ttf, .xml, ...` (`is_valid_url()`,
   kiem tra `config.IGNORED_EXTENSIONS`)
5. Chi giu URL cung domain duoc phep (`ALLOWED_DOMAINS`) - so sanh domain
   sau khi da bo tien to `www.` de coi `www.globaltimes.cn` va
   `globaltimes.cn` la 1 (`is_allowed_domain()`)
6. Kiem tra `robots.txt` (`can_fetch`) truoc khi thuc su gui request
   (`crawler.py`, `_can_fetch()`)
7. Chi them vao Frontier neu `depth + 1 <= MAX_DEPTH`

Neu URL khong vuot qua duoc buoc nao trong so nay, no khong bao gio duoc
gui request toi — tiet kiem thoi gian/bang thong va tranh bi chan.

## 6. Content Filtering Rules (Loc ben trong — sau khi tai trang ve)

Day la phan moi bo sung so voi ban dau: ngay ca khi 1 URL da vuot qua het
cac buoc loc o Muc 5 va duoc tai ve thanh cong (HTTP 200), noi dung trang
do van co the KHONG phai la 1 bai viet tin tuc that su (vi du: trang chu,
trang danh muc/section, trang tag) — hoac trang thuc su la bai viet nhung
HTML cua no con lan banner quang cao, menu dieu huong, box "bai viet lien
quan" ma khong loc thi se bi dinh vao content luu trong database. Xu ly
trong ham `extract_page_info()` (`parser.py`), theo 3 buoc:

**Buoc 1 - Loai bo khoi khong phai noi dung (`EXCLUDE_SELECTORS`):**
truoc khi trich text, cac the `<nav>`, `<header>`, `<footer>`, `<script>`,
`<style>`, cac class lien quan quang cao/chia se/box lien quan
(`.related`, `.share`, `.ad`, ...) bi xoa hoan toan khoi cay HTML bang
`tag.decompose()`.

**Buoc 2 - Uu tien lay dung khoi bai viet (`ARTICLE_CONTENT_SELECTORS`):**
thay vi lay text cua ca trang (`soup.get_text()`), code thu tim khoi HTML
bao dung phan bai viet, theo thu tu uu tien:

```python
ARTICLE_CONTENT_SELECTORS = [
    ".article_content",   # class THAT cua globaltimes.cn
    "article",
    "#Content",
]
```

Selector `.article_content` duoc xac dinh bang cach mo 1 bai viet that
tren globaltimes.cn, bam chuot phai vao doan van ban -> Inspect (F12), roi
doc cay DOM di len tu doan van do: `div.article_page > div.article >
div.article_content` la khoi bao dung toan bo phan than bai (khong bao
gom `div.article_top` la tieu de/ngay thang, va khong bao gom
`div.article_left` la sidebar — ca hai deu nam NGOAI `article_content`
nen tu dong bi loai).

**Buoc 3 - Bat buoc phai khop (`REQUIRE_ARTICLE_MATCH = True`):** neu
khong tim thay khoi nao khop `ARTICLE_CONTENT_SELECTORS` (tuc day khong
phai trang bai viet, vi du trang chu/trang danh muc), ham `extract_page_info()`
tra ve `None` thay vi mot page_info rong. `crawler.py` khi nhan duoc `None`
se **khong luu trang do vao bang `pages`**, nhung **van trich link tu
trang do** de BFS tiep tuc di sau vao cac bai viet nam ben trong (trang
danh muc thuong chua link toi rat nhieu bai viet that).

Ngoai ra, sau khi da co content sach, neu do dai con lai duoi
`MIN_CONTENT_LENGTH = 500` ky tu (truong hop hiem, selector khop nhung
noi dung that su rat ngan) thi cung bi bo qua, khong luu — day la lop
kiem tra an toan cuoi cung dam bao khong co dong "rac" nao lot vao
database.

**Ve trang loi (status khac 200):** cac request tra ve 404/403/500...
chi duoc tinh vao thong ke `Failed Requests`, **khong con duoc luu vao
bang `pages`** nua (khac ban dau, truoc day van INSERT ca dong voi
title/content rong).

Tom lai: **du lieu chi duoc ghi vao bang `pages` khi ca 2 tang loc deu
qua** — URL hop le (Muc 5) VA noi dung xac dinh la bai viet that, du dai
toi thieu (Muc 6). Bang `links` thi van ghi nhan toan bo lien ket phat
hien duoc (Task 8), bat ke trang nguon co duoc luu vao `pages` hay khong,
de giu day du du lieu ve cau truc lien ket cua site.

## 7. Database Design

SQLite tai `data/crawler.db`, 2 bang:

- **`pages`**: luu thong tin tung bai viet that su da qua het 2 tang loc
  o Muc 5 va Muc 6 (url, domain, title, content, depth, status_code,
  crawled_at). Cot `url` co rang buoc `UNIQUE` de chinh tang co so du
  lieu cung chong duoc du lieu trung.
- **`links`**: luu quan he "trang nao link toi trang nao"
  (source_url, target_url), phuc vu phan tich cau truc lien ket sau nay -
  ghi nhan toan bo link phat hien, khong phu thuoc viec trang nguon co
  duoc luu vao `pages` hay khong.

## 8. Crawling Results

*(Dien ket qua thuc te sau khi ban chay `python main.py` tren may co ket
noi internet - chuong trinh se tu in phan CRAWLING SUMMARY o cuoi.)*

```
Pages Crawled          : ...
Unique URLs Discovered : ...
Skipped URLs           : ...
Failed Requests        : ...
```

---

## Cach chay

```bash
pip install -r requirements.txt
python main.py
```

Chay file **`main.py`** — day la entry point duy nhat, no se tu dong goi
`crawler.py`, `url_frontier.py`, `parser.py`, `database.py` theo dung thu
tu trong pipeline (Task 9). Ket qua duoc luu tai `data/crawler.db`.

## Project Structure

```
web-crawler-globaltime/
├── main.py          # Entry point - chay file nay
├── crawler.py        # HTTP request, robots.txt, vong lap crawl chinh, loc trang loi/khong phai bai viet
├── url_frontier.py   # URL Frontier (BFS queue + visited set)
├── parser.py          # Trich xuat thong tin trang (loc noi dung) + trich/loc hyperlink (loc URL)
├── database.py        # Luu du lieu vao SQLite (bang pages, links)
├── config.py          # Cau hinh crawl (seed, domain, depth, delay, cac selector loc noi dung...)
├── data/
│   └── crawler.db     # Duoc tao tu dong khi chay
├── requirements.txt
└── README.md
```
