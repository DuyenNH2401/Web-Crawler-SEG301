# Focused Web Crawler - SEG301 Assignment

Crawler tap trung (focused web crawler) viet bang Python, dung `requests` +
`BeautifulSoup` de crawl trang, va SQLite de luu du lieu. Crawl theo thu tu
BFS (Breadth-First Search) qua URL Frontier.

> **QUAN TRONG - doc truoc khi nop bai:** de bai yeu cau chon **toi thieu 2
> domain** trong cung 1 topic ("You should select at least 2 domains from
> your chosen topic"). File `config.py` trong repo nay hien **chi cau hinh
> 1 domain la BBC (bbc.com)** de ban test truoc. Truoc khi nop, hay them
> domain thu 2 (vi du CNN hoac The Guardian - cung la domain chinh thuc
> trong bang de bai cho topic News & Information) vao ca `SEED_URLS` va
> `ALLOWED_DOMAINS` trong `config.py`.

## 1. Selected Topic and Domains

- **Topic:** News & Information
- **Domain (dang cau hinh):** BBC — `bbc.com`

**Vi sao chon BBC ma khong phai NPR:** ban dau du dinh crawl NPR, nhung khi
test thuc te NPR chan ket noi ngay o tang TLS handshake
(`ConnectionResetError` xay ra truoc khi kip nhan response) - day la kieu
chan dua tren "TLS fingerprint" cua client, khong the sua duoc chi bang
`requests` + header thong thuong (nam ngoai kha nang cua cac cong nghe de
bai cho phep). BBC nam trong danh sach domain **chinh thuc** cua de bai va
da co nhieu tien le crawl thanh cong bang dung `requests` + `BeautifulSoup`.

Crawler nay dung `urllib.robotparser` de tu dong kiem tra `robots.txt` cua
domain truoc moi request (khong hardcode luat), nen se tu dong bo qua bat
ky duong dan nao bi cam. Truoc khi crawl, nen tu kiem tra nhanh bang trinh
duyet tai `https://www.bbc.com/robots.txt` de biet truoc cac gioi han.

## 2. Seed URLs

```
https://www.bbc.com/
https://www.bbc.com/news
```

## 3. Crawling Configuration

Cau hinh tap trung trong [`config.py`](config.py):

| Parameter | Value |
| :--- | :--- |
| Maximum Depth | 3 |
| Maximum Pages | 100 |
| Request Timeout | 20 giay |
| Crawl Delay | 1.5 giay |

Ly do chon Crawl Delay 1.5s: de dam bao lich su, tranh gui request qua
nhanh gay tai cho server va giam nguy co bi chan boi cac lop chong bot -
nen kiem tra lai `Crawl-delay` thuc te trong `robots.txt` cua domain minh
chon va dieu chinh neu can. Request Timeout duoc dat 20s (thay vi 10s mac
dinh) vi route mang quoc te co the co do tre cao hon binh thuong.

## 4. Crawling Strategy

URL Frontier (`url_frontier.py`) dung `collections.deque` de dam bao thu
tu BFS: cac trang o depth thap hon luon duoc crawl truoc cac trang o depth
cao hon. Frontier dong thoi giu 1 `set` cac URL dang cho (`_queued_set`) va
1 `set` cac URL da crawl (`visited`) de khong bao gio them 2 lan cung 1 URL
vao hang doi, va khong crawl lai URL da xu ly (Task 7 - tranh duplicate).

Vong lap chinh dung khi **mot trong hai dieu kien** xay ra truoc: so trang
da crawl thanh cong dat `MAX_PAGES`, hoac Frontier rong (khong con URL nao
de crawl).

## 5. URL Filtering Rules

Trong `parser.py`, moi link trich xuat tu the `<a href>` phai vuot qua het
cac buoc loc sau moi duoc them vao Frontier:

1. Bo qua scheme khong phai web: `mailto:`, `javascript:`, `tel:`, `ftp:`
2. Chuyen URL tuong doi thanh URL tuyet doi bang `urljoin(current_url, href)`
3. Chuan hoa URL: bo fragment (`#...`), bo dau `/` thua o cuoi path
4. Bo qua file khong phai HTML dua tren duoi file: `.jpg, .png, .css, .js,
   .pdf, .zip, .mp3, .mp4, ...`
5. Chi giu URL cung domain duoc phep (`ALLOWED_DOMAINS`) - so sanh domain
   sau khi da bo tien to `www.` de coi `www.bbc.com` va `bbc.com` la 1
6. Kiem tra `robots.txt` (`can_fetch`) truoc khi thuc su gui request
7. Chi them vao Frontier neu `depth + 1 <= MAX_DEPTH`

## 6. Database Design

SQLite tai `data/crawler.db`, 2 bang:

- **`pages`**: luu thong tin tung trang da crawl thanh cong hoac loi
  (url, domain, title, content, depth, status_code, crawled_at). Cot
  `url` co rang buoc `UNIQUE` de chinh tang co so du lieu cung chong duoc
  du lieu trung.
- **`links`**: luu quan he "trang nao link toi trang nao"
  (source_url, target_url), phuc vu phan tich cau truc lien ket sau nay.

## 7. Crawling Results

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
web-crawler-bbc/
├── main.py          # Entry point - chay file nay
├── crawler.py        # HTTP request, robots.txt, vong lap crawl chinh
├── url_frontier.py   # URL Frontier (BFS queue + visited set)
├── parser.py          # Trich xuat thong tin trang + trich/loc hyperlink
├── database.py        # Luu du lieu vao SQLite (bang pages, links)
├── config.py          # Cau hinh crawl (seed, domain, depth, delay...)
├── data/
│   └── crawler.db     # Duoc tao tu dong khi chay
├── requirements.txt
└── README.md
```
