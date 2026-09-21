# Focused Web Crawler - SEG301 Lab Project

A focused, polite web crawler built with Python, Requests, BeautifulSoup, and SQLite for the **SEG301 - Information Retrieval & Search Engines** course (Chapter 3: *Crawls and Feeds*).

---

## 1. Selected Topic and Domains

- **Topic:** News & Information
- **Selected Domain:**
  - `e.vnexpress.net` (VnExpress International - The most-read English news publication in Vietnam)

---

## 2. Seed URLs

The crawling process initiates from the seed URL:
1. `https://e.vnexpress.net/`

---

## 3. Crawling Configuration

The configuration parameters are centralized in [`config.py`](config.py):

| Parameter | Value | Description |
| :--- | :--- | :--- |
| **Topic** | `News & Information` | Selected topic domain |
| **Allowed Domains (`ALLOWED_DOMAINS`)** | `["e.vnexpress.net"]` | Domain constraint to keep crawler focused |
| **Articles Only (`ARTICLES_ONLY`)** | `True` | Bắt buộc cào bài báo thực sự (đuôi `.html` và có mã bài viết) |
| **Maximum Pages (`MAX_PAGES`)** | `100` | Stopping threshold for downloaded web pages |
| **Maximum Depth (`MAX_DEPTH`)** | `3` | Maximum hop distance from seed URLs (Seed URL is depth 0) |
| **Request Timeout (`REQUEST_TIMEOUT`)** | `10` seconds | Socket read/connect timeout per HTTP request |
| **Crawl Delay (`CRAWL_DELAY`)** | `1.0` second | Polite delay interval between requests |
| **Storage (`DB_PATH`)** | `data/crawler.db` | SQLite database file |

---

## 4. Crawling Strategy

### 4.1 Breadth-First Search (BFS)
This crawler adopts a **Breadth-First Search (BFS)** crawling policy instead of Depth-First Search (DFS) for key reasons:
1. **Article Prioritization:** Starting from the seed homepage, the crawler identifies and enqueues high-priority news articles at depth 1.
2. **Avoiding Spider Traps:** Prevents the crawler from getting stuck in deep pagination loops or recursive archive links.
3. **Queue Discipline:** URLs discovered earlier are prioritized before diving into deeper article sub-trees.

### 4.2 URL Frontier Architecture
The URL Frontier is implemented in [`url_frontier.py`](url_frontier.py) using Python's double-ended queue (`collections.deque`):
- **FIFO Queue:** Elements are popped from the left (`popleft()`) and appended to the right (`append()`), guaranteeing BFS traversal.
- **Tuples:** Stores `(url, depth)` pairs to maintain strict depth bookkeeping.
- **Seen & Visited Sets:** $O(1)$ lookups to immediately skip previously seen or already crawled URLs.

---

## 5. URL Filtering Rules

To ensure high-quality crawling and prevent downloading irrelevant category listings, links extracted via `<a href>` undergo multi-stage filtering in [`parser.py`](parser.py):

1. **Article Verification (`is_article_url`):**
   - **Bắt buộc đuôi `.html`:** Chỉ thu thập các đường dẫn bài viết thực sự (ví dụ `...-south-korea-s-second-largest-city-welcomes-3-million-tourists-in-seven-months-5122661.html`).
   - **Loại bỏ trang danh mục:** Hoàn toàn bỏ qua các trang danh mục / chuyên mục không có đuôi `.html` (như `/news/life/wellness`, `/news/news`, `/news/business/economy`, `/interactive/...`).
   - **Loại bỏ trang lỗi:** Bỏ qua `/error.html`.
2. **Relative URL Normalization:** Uses `urllib.parse.urljoin(current_url, href)` to convert relative links into fully qualified absolute URLs.
3. **Anchor & Fragment Removal:** Fragments (e.g., `#box_comment`, `#header`) are stripped so duplicate anchors point to the same canonical URL.
4. **Domain Whitelist (`ALLOWED_DOMAINS`):** Only URLs belonging to `e.vnexpress.net` are accepted. Outbound links to social networks or third parties are discarded.
5. **Scheme Whitelist:** Only standard `http` and `https` protocols are accepted (`mailto:`, `javascript:`, and `tel:` are rejected).
6. **Static Asset Filtering:** Non-HTML files are ignored (`.jpg`, `.jpeg`, `.png`, `.gif`, `.svg`, `.css`, `.js`, `.pdf`, `.zip`, `.mp4`, etc.).
7. **Robots.txt Compliance:** Before dispatching an HTTP GET request, the crawler queries the cached `RobotFileParser` for that domain to verify access permissions.

---

## 6. Database Design

Data is persistently stored in SQLite (`data/crawler.db`) adhering to the schema specified in Task 8:

### Table 1: `pages`
Stores the metadata and text content extracted from each successfully crawled HTML page.

```sql
CREATE TABLE pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE,
    domain TEXT,
    title TEXT,
    content TEXT,
    depth INTEGER,
    status_code INTEGER,
    crawled_at TEXT
);
```

- `url`: Canonical URL of the page (marked `UNIQUE` to ensure idempotency).
- `domain`: Host domain name (`e.vnexpress.net`).
- `title`: Extracted `<title>` or article headline (`h1`).
- `content`: Cleaned, visible body text (scripts/styles stripped out, lead summary + article paragraphs).
- `depth`: Depth level at which the page was discovered (0 for seed).
- `status_code`: HTTP response status code (e.g., 200).
- `crawled_at`: ISO 8601 formatted crawl timestamp.

### Table 2: `links`
Represents the directed web graph by storing the relationships between crawled pages and their discovered outbound hyperlinks.

```sql
CREATE TABLE links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url TEXT,
    target_url TEXT
);
```

---

## 7. How to Install and Run

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Run the Crawler
To run with default settings (`MAX_PAGES = 100`, `MAX_DEPTH = 3`):
```bash
python main.py
```

Optional CLI parameters:
```bash
# Quick test run with 10 pages and depth 2
python main.py --max-pages 10 --max-depth 2 --delay 0.5

# Reset existing database and start fresh
python main.py --reset-db
```

### Step 3: Inspect Crawled Articles
```bash
# View overview table
python view_db.py

# Read a specific article by ID
python view_db.py --read 2
```

---

## 8. Crawling Results

*(The statistics below are dynamically computed from `crawler.db` upon completion)*

```text
========== CRAWLING SUMMARY ==========
Topic                  : News & Information
Seed URLs              : 1
Pages Crawled          : 100
Unique URLs Discovered : ...
Skipped URLs           : ...
Failed Requests        : ...
Maximum Depth          : 3

Depth 0                : 1 pages
Depth 1                : ... pages
Depth 2                : ... pages
Depth 3                : ... pages

HTTP 200               : ...
HTTP 404               : ...
HTTP 403               : ...
=======================================
```
