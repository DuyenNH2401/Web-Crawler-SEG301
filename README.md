# Multi-source Focused Web Crawler - SEG301 Lab Project

A focused, polite web crawler built with Python, Requests, BeautifulSoup, and SQLite for the **SEG301 - Information Retrieval & Search Engines** course (Chapter 3: *Crawls and Feeds*).

---

## 1. Selected Topic and Sources

- **Topic:** News & Information
<<<<<<< HEAD
- **Selected Domain:**
  - `bbc.com` / `bbc.co.uk` (BBC News)
=======
- **Sources:** VnExpress, CNN, BBC, The Guardian, and Global Times
- Each source keeps its original URL rules and HTML parser in [`sources/`](sources/).
- All parsers return one common `Article` format before digest generation.
>>>>>>> 73c7225514e14883d3bf6cd6a00bb4611de504c1

---

## 2. Seed URLs

<<<<<<< HEAD
The crawling process initiates from the seed URL:
1. `https://www.bbc.co.uk/business` (redirects to the BBC Business section)
=======
Runtime settings for all five sources, including seed URLs, domains, headers,
limits, and delays, are in [`config.py`](config.py). The five crawlers still
run independently so one source's URL rules cannot affect another source's
frontier.
>>>>>>> 73c7225514e14883d3bf6cd6a00bb4611de504c1

---

## 3. Crawling Configuration

The configuration parameters are centralized in [`config.py`](config.py):

| Parameter | Value | Description |
| :--- | :--- | :--- |
| **Topic** | `News & Information` | Selected topic domain |
<<<<<<< HEAD
| **Allowed Domains (`ALLOWED_DOMAINS`)** | `["bbc.com", "bbc.co.uk"]` | Domain constraint to keep crawler focused |
| **Articles Only (`ARTICLES_ONLY`)** | `False` | Follow articles and useful topic/index pages; reject media and utility routes |
| **Maximum Pages (`MAX_PAGES`)** | `100` | Stopping threshold for downloaded web pages |
| **Maximum Depth (`MAX_DEPTH`)** | `3` | Maximum hop distance from seed URLs (Seed URL is depth 0) |
| **Request Timeout (`REQUEST_TIMEOUT`)** | `10` seconds | Socket read/connect timeout per HTTP request |
| **Crawl Delay (`CRAWL_DELAY`)** | `1.0` second | Polite delay interval between requests |
| **Storage (`DB_PATH`)** | `data/crawler.db` | SQLite database file |
=======
| **Sources** | `5` | One adapter per newspaper |
| **Maximum Pages (`--max-pages`)** | Source config (`100/source`) | Optional global override |
| **Articles (`--articles-per-source`)** | `1/source` | Number of articles included in the digest |
| **Maximum Depth (`--max-depth`)** | Source-specific | Preserves each original branch rule |
| **Delay (`--delay`)** | Source-specific | Optional global override |
| **Storage** | `data/crawler.db` | Pages, links, and combined digests |
>>>>>>> 73c7225514e14883d3bf6cd6a00bb4611de504c1

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

To ensure high-quality crawling and prevent downloading irrelevant pages, each
source adapter applies the original branch-specific rules. The shared engine
does not decide whether a URL is an article; it delegates that decision to the
active adapter.

<<<<<<< HEAD
1. **Page Eligibility:**
   - Accepts useful BBC article, topic, section, and live-text pages linked from the page's `<main>` content.
   - Uses current and legacy article URL formats to select the article-body extraction strategy.
   - Rejects video, image-gallery, audio, programme, search, feed, and other media/utility routes.
2. **Relative URL Normalization:** Uses `urllib.parse.urljoin(current_url, href)` to convert relative links into fully qualified absolute URLs.
3. **Anchor & Fragment Removal:** Fragments (e.g., `#box_comment`, `#header`) are stripped so duplicate anchors point to the same canonical URL.
4. **Domain Whitelist (`ALLOWED_DOMAINS`):** Only BBC hosts are accepted. Outbound links to social networks or third parties are discarded.
5. **Scheme Whitelist:** Only standard `http` and `https` protocols are accepted (`mailto:`, `javascript:`, and `tel:` are rejected).
6. **Static Asset Filtering:** Non-HTML files are ignored (`.jpg`, `.jpeg`, `.png`, `.gif`, `.svg`, `.css`, `.js`, `.pdf`, `.zip`, `.mp4`, etc.).
7. **Robots.txt Compliance:** Before dispatching an HTTP GET request, the crawler queries the cached `RobotFileParser` for that domain to verify access permissions.
=======
1. **Source-specific article verification:** Each adapter retains its original URL pattern, including VnExpress `.html` IDs, CNN date paths, BBC article IDs, and the Guardian/Global Times rules.
2. **Relative URL normalization:** Each adapter converts relative links into absolute URLs using its original normalization logic.
3. **Domain and scheme filtering:** Each adapter applies its original allowed-domain, blocked-path, blocked-subdomain, and static-asset rules.
4. **Robots.txt compliance:** Before an HTTP GET, the shared engine checks the cached `RobotFileParser` for that source.
>>>>>>> 73c7225514e14883d3bf6cd6a00bb4611de504c1

---

## 6. Database Design

Data is persistently stored in SQLite (`data/crawler.db`) using the common page,
link, and digest tables. After crawling, [`digest.py`](digest.py) combines the
articles and the result is stored in the `digests` table.

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
- `domain`: BBC host domain name (for example `www.bbc.com`).
- `title`: Extracted `<title>` or article headline (`h1`).
- `content`: Clean editorial text only: article body paragraphs, or valid text-article headlines on a topic page. Media, captions, ads, bylines, and navigation are excluded.
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

### Table 3: `digests`
Stores one combined digest for each crawl run.

```sql
CREATE TABLE digests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT,
    content TEXT,
    article_count INTEGER,
    created_at TEXT
);
```

---

## 7. How to Install and Run

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Run the Crawler
To run with the default source-specific settings:
```bash
python3 main.py
```

Optional CLI parameters:
```bash
# Quick run with 10 pages per source and one article per source
python3 main.py --max-pages 10 --articles-per-source 1 --delay 0.5

# Reset existing database and start fresh
python3 main.py --reset-db
```

### Step 3: Inspect Crawled Articles
```bash
# View overview table
python3 view_db.py

# Read a specific article by ID
python3 view_db.py --read 2

# Read the latest combined digest
sqlite3 data/crawler.db "SELECT content FROM digests ORDER BY id DESC LIMIT 1;"
```

---

## 8. Crawling Results

*(The crawl statistics are printed per source; the combined output is stored in `data/crawler.db`.)*

```text
========== CRAWLING SUMMARY ==========
Topic                  : News & Information
Sources                : 5
Articles in digest     : 5 by default
Digest                 : `digests` table in `data/crawler.db`
=======================================
```
