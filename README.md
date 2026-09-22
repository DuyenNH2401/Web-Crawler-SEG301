# Focused Web Crawler — SEG301

A breadth-first focused web crawler that starts from seed URLs, follows in-domain
hyperlinks, extracts page content with BeautifulSoup, and stores the results in SQLite.

---

## 1. Selected topic

```
Topic: News & Information

Domain:
- The Guardian   (theguardian.com)
```

### Note on the number of domains

Section 3 of the assignment says to select **at least 2 domains** from the chosen topic.
This crawl deliberately uses **one** domain — The Guardian — to keep the collected corpus
single-source.

`config.py` is set up so the crawl can be widened without touching any crawler logic:
BBC is present as a commented-out entry in `DOMAINS`, `SEED_URLS` and `ALLOWED_DOMAINS`.
Uncommenting those three lines produces a two-domain crawl.

### Domain accessibility check

The assignment requires checking `robots.txt` and technical accessibility before
committing to a domain. All four News & Information candidates were probed:

| Domain | robots.txt allows seed | HTTP status | Verdict |
|---|---|---|---|
| The Guardian | yes | 200 | **selected** |
| BBC | yes | 200 | verified, kept commented out |
| CNN | yes | 200 | usable, not needed |
| Reuters | **no** | **401** | **rejected** |

Reuters was rejected on two independent grounds: its `robots.txt` disallows the seed page
for our user-agent, and the site answers `HTTP 401 Unauthorized` to a plain request.

The Guardian serves fully server-rendered HTML — article pages return `200` with 110–125
extractable anchors each, so the crawl does not stall at depth 1 the way a
JavaScript-rendered site would.

**Terms of use.** `theguardian.com/robots.txt` allows `User-agent: *` for the article
paths crawled here. Its header comment additionally reserves content against LLM,
machine-learning and commercial use; this crawl is coursework — it collects a small
sample for an academic exercise, trains nothing, and is not commercial.

---

## 2. Seed URLs

```
1. https://www.theguardian.com/international
2. https://www.theguardian.com/world
```

Both are section index pages rather than the site root, so depth 1 lands directly on news
articles instead of on corporate navigation. Two seeds rather than one gives the frontier
two independent entry points, which makes the breadth-first ordering visible in the log.

---

## 3. Crawling configuration

Defined in `config.py`:

```
Maximum pages  : 100
Maximum depth  : 2        (seeds are depth 0)
Request timeout: 10 seconds
Crawl delay    : 1 second
Respect robots : True
User-Agent     : SEG301-StudentCrawler/1.0
```

Any value can be overridden on the command line without editing the file:

```bash
python main.py --max-pages 20 --max-depth 1 --delay 2
```

### Why a 1-second delay

`theguardian.com/robots.txt` declares no `Crawl-delay`, so the crawler must choose a
courteous default. One second between requests caps the crawl at 60 requests/minute — far
below what the Guardian's CDN handles, and low enough that a 100-page run adds no
measurable load. The delay is enforced *between* requests by measuring elapsed time since
the last one, so a slow response does not cause an extra wait on top of the time already
spent.

---

## 4. Crawling strategy

### Why BFS

Breadth-first search explores every page at depth *N* before any page at depth *N+1*.
For a focused crawl this matters because pages closer to a seed are the higher-value
ones: a news section page links to today's headlines, which link to related articles,
which eventually link to archive pages from years ago. BFS spends the page budget on the
most relevant layer first.

Depth-first would instead chase a single link chain deep into one section, producing a
narrow, unrepresentative sample and reaching `MAX_PAGES` without ever visiting the second
seed.

### How the URL Frontier works

`url_frontier.py` implements the frontier as a `collections.deque` of `(url, depth)`
pairs:

- new URLs are appended on the **right** (`append`)
- the next URL is taken from the **left** (`popleft`)

Because a queue is FIFO, everything already enqueued at depth *N* is handed out before
anything discovered at depth *N+1* — that property alone is what makes the traversal
breadth-first. The run log confirms it: crawls #001 and #002 are the two depth-0 seeds,
and every page from #003 onward is depth 1.

Three collections are maintained:

| Collection | Purpose |
|---|---|
| `_queue` | URLs waiting to be crawled, each with its depth |
| `visited` | URLs already fetched |
| `seen` | queued **and** visited — the duplicate test |

Checking against `seen` rather than `visited` prevents the same URL being queued twice
before it has been fetched even once. On a news site, where every article links back to
the section index and to the same set of navigation targets, this removes a large amount
of redundant work.

### Depth control

Each frontier entry carries its own depth. After a page at depth *d* is parsed, its links
are only enqueued when `d + 1 <= MAX_DEPTH`. Links discovered on a page already at the
depth limit are still parsed and recorded in the `links` table, but never queued, so the
crawl cannot run away.

### Stopping conditions

The crawl stops when **either**:

1. `MAX_PAGES` successfully stored pages is reached, or
2. the URL frontier is empty.

Both conditions are exercised in the runs below — the main run stops on `MAX_PAGES`, the
depth-demonstration run stops on an empty frontier.

---

## 5. URL filtering rules

Implemented in `parser.py`. Every extracted `href` is first made absolute with
`urljoin(current_url, href)`, then normalized, then tested. A URL is **rejected** when any
of the following holds:

| Rule | Rejected example | Reason recorded |
|---|---|---|
| Non-HTTP scheme | `mailto:`, `javascript:`, `tel:`, `ftp:` | `non-http scheme` |
| Outside allowed domains | `https://facebook.com/guardian` | `outside allowed domains` |
| Non-editorial subdomain | `holidays.theguardian.com` | `non-editorial subdomain` |
| Non-web resource | `.jpg .png .css .js .zip .pdf …` | `non-web resource` |
| Off-topic site section | `/crosswords`, `/jobs`, `/subscribe` | `blocked path` |
| Already seen | any previously queued or visited URL | `already visited` |
| Disallowed by robots.txt | checked per-host before fetching | `robots.txt` |
| Not HTML | response `Content-Type` lacks `html` | `not HTML` |
| Duplicate content | MD5 of extracted text already stored | `duplicate content` |

### The domain rule

The assignment warns that `example.com`, `www.example.com` and `sub.example.com` must be
handled deliberately. The rule used here:

> A URL is in scope when its host, after stripping a leading `www.`, either **equals** an
> entry in `ALLOWED_DOMAINS` or **ends with `.` + that entry**.

So `theguardian.com`, `www.theguardian.com` and `amp.theguardian.com` are all accepted.
The `.` in the suffix test is what makes this safe — a naive
`host.endswith("theguardian.com")` would also accept a hostile
`theguardian.com.example.net`, whereas requiring `.theguardian.com` does not.

### Why a subdomain blocklist was needed

That rule alone proved too permissive in practice. A first full run stored pages from
`support.theguardian.com` and `holidays.theguardian.com` — the subscription funnel and a
holiday-booking shop. Both are genuinely on-domain, and both carry no journalism, which
defeats the point of a *focused* news crawl.

`BLOCKED_SUBDOMAINS` therefore excludes the non-editorial hosts the Guardian runs on its
own domain: `holidays`, `support`, `manage`, `profile`, `jobs`, `patrons`, `syndication`
and the advertising sites. The test compares the **whole first label**, not a prefix, so a
hypothetical `supportive.theguardian.com` is not caught by the `support` entry. After the
fix, all 100 stored pages come from `www.theguardian.com`.

### URL normalization

Before any duplicate test, `normalize_url()` applies:

- lowercase the scheme and host (paths stay case-sensitive — many CMSs are)
- drop the `#fragment` (`/article#comments` is the same page as `/article`)
- drop a default port (`:80`, `:443`)
- drop a trailing slash, except on the site root

This is what collapses the assignment's example of `…/news/1` and `…/news/1/` into one
URL, and prevents the crawler spending its page budget re-fetching the same content.

### "Focused" crawling

`BLOCKED_PATH_PREFIXES` is what makes this a *focused* rather than a general crawler.
`theguardian.com` hosts crosswords, a video player, photo galleries, a jobs board, author
profile pages and the subscription funnel alongside its journalism. Those sections are
on-domain and would otherwise be crawled, but carry no article text.

Paths already `Disallow`ed by the Guardian's own `robots.txt` (`/search`, `/discussion`,
`/email`, `/print`, `/preference`, `/sections`) are **not** duplicated in that list — the
robots check rejects them first.

---

## 6. Database design

SQLite database at `data/crawler.db`, two tables.

### `pages` — one row per successfully crawled page

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | auto-increment |
| `url` | TEXT **UNIQUE** | normalized page URL |
| `domain` | TEXT | host, for per-site statistics |
| `title` | TEXT | `<title>` text |
| `content` | TEXT | visible text, boilerplate removed |
| `depth` | INTEGER | link distance from a seed |
| `status_code` | INTEGER | HTTP status |
| `crawled_at` | TEXT | ISO-8601 timestamp |

**Purpose:** the document store. This is the corpus the next assignment will tokenize and
index. The `UNIQUE` constraint on `url` is a second line of defence behind the in-memory
`seen` set — combined with `INSERT OR IGNORE`, a duplicate URL can never produce a
duplicate row even if the in-memory check were bypassed.

`content` is stripped of `script`, `style`, `nav`, `header`, `footer`, `aside` and `form`
before the text is taken, so what is stored is closer to article text than to navigation
chrome. It is truncated at `MAX_CONTENT_CHARS` (20 000) to keep the database a sensible
size. Across the 100 stored pages the average is 6 746 characters, and every page has a
non-empty title.

### `links` — one row per hyperlink found

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | auto-increment |
| `source_url` | TEXT | page the link was found on |
| `target_url` | TEXT | link destination |

**Purpose:** the web graph. `pages` records *what* was collected; `links` records *how the
pages connect*. Every discovered link is stored, including ones the filter rejected,
because the graph is only meaningful if outbound edges are not silently dropped. This
table is what would make link-based ranking (PageRank, HITS) or broken-link analysis
possible later.

Two indexes (`idx_links_source`, `idx_pages_depth`) speed up the per-source and per-depth
queries used by the statistics.

---

## 7. Crawling results

Full run, `python main.py`, default configuration:

```
=========================================
           CRAWLING SUMMARY
=========================================
Topic                  : News & Information
Domains                : The Guardian
Seed URLs              : 2
Pages Crawled          : 100
Unique URLs Discovered : 2034
Skipped URLs           : 3964
Failed Requests        : 0
Duplicate Content      : 2
Maximum Depth          : 1 (limit 2)
Frontier Remaining     : 1931
Total Time             : 130.6 seconds
-----------------------------------------
Depth 0                : 2 pages
Depth 1                : 98 pages
-----------------------------------------
HTTP 200               : 102
-----------------------------------------
Skip reasons:
  blocked path          : 1781
  outside allowed domains: 1339
  non-editorial subdomain: 781
  non-http scheme       : 59
  duplicate content     : 2
  robots.txt            : 1
  non-web resource      : 1
-----------------------------------------
Pages stored per domain:
  www.theguardian.com   : 100
-----------------------------------------
Database               : data/crawler.db
  pages rows           : 100
  links rows           : 13955
=========================================
```

All figures are computed from the crawl by `Crawler.print_summary()` and read back out of
SQLite; none are entered by hand.

### Reading the skip counts

`Skipped URLs` counts **rejection events, not distinct URLs**. A link that appears in the
Guardian's site-wide navigation is re-extracted and re-rejected on every page it appears
on, so one blocked URL can contribute a hundred rejections. Across the whole run there
were 3 964 rejection events but only ~160 distinct blocked-path URLs behind them. The
counter is deliberately per-event, because what it measures is how much work the filter
saved the fetcher.

`HTTP 200 : 102` against `Pages Crawled : 100` is also expected: two pages returned 200 and
were parsed, then discarded by the duplicate-content check before storage.

### Why maximum depth is 1, not 2

Each Guardian page yields roughly 80 in-scope links, so the two seeds alone put ~150 URLs
into the frontier at depth 1. Breadth-first order means all of depth 1 must be crawled
before depth 2 begins — and the 100-page budget runs out long before that. 1 931 URLs were
still waiting in the frontier when the crawl stopped.

This is correct BFS behaviour, not a bug: `MAX_DEPTH` is a safety bound, not a target.
But it does mean the default run never exercises the depth limit.

### Depth-limit demonstration

To show depth control actually working, `MAX_LINKS_PER_PAGE` caps how many links each page
contributes to the frontier, making the crawl descend instead of fan out. It defaults to
`0` (unlimited — the honest breadth-first sample above); the run below sets it to 5:

```bash
python main.py --max-pages 40 --max-depth 3 --links-per-page 5 --delay 0.6
```

```
Pages Crawled          : 15
Unique URLs Discovered : 16
Skipped URLs           : 601
Failed Requests        : 0
Maximum Depth          : 3 (limit 3)
Frontier Remaining     : 0
-----------------------------------------
Depth 0                : 2 pages
Depth 1                : 7 pages
Depth 2                : 5 pages
Depth 3                : 1 pages
```

This run confirms three things the default run cannot:

- **the depth limit binds** — nothing beyond depth 3 was crawled
- **the second stopping condition works** — it ended on an empty frontier, not `MAX_PAGES`
- **BFS order holds across four levels** — all of depth *N* precedes any of depth *N+1*

---

## 8. Project structure

```
assignment1/
│
├── main.py            entry point, config banner, CLI overrides
├── crawler.py         Tasks 3, 6, 9 — fetch loop, robots.txt, statistics
├── url_frontier.py    Tasks 2, 6, 7 — BFS deque, visited/seen sets
├── parser.py          Tasks 4, 5, 7 — page data, link extraction, filtering
├── database.py        Task 8 — SQLite schema and queries
├── config.py          Task 1 — all crawl parameters
│
├── reader.py          read-only API over the crawl database
├── query.py           command-line inspector built for quick looks
│
├── data/
│   └── crawler.db
│
├── requirements.txt
└── README.md
```

### Task-to-file map

| Task | Where |
|---|---|
| 1 — Seed URLs & configuration | `config.py`, `main.print_configuration()` |
| 2 — URL Frontier | `url_frontier.URLFrontier` |
| 3 — Crawl pages | `crawler.Crawler.fetch()` |
| 4 — Extract page info | `parser.extract_page_data()` |
| 5 — Extract & filter links | `parser.extract_links()`, `parser.is_crawlable()` |
| 6 — Depth control | `crawler._crawl_one()`, frontier `(url, depth)` pairs |
| 7 — Avoid duplicates | `parser.normalize_url()`, frontier `seen`, MD5 checksum |
| 8 — SQLite storage | `database.Database` |
| 9 — Complete crawler | `crawler.Crawler.crawl()` |
| Statistics | `crawler.Crawler.print_summary()` |

---

## 9. How to run

```bash
pip install -r requirements.txt

# full run, using config.py
python main.py

# short run for testing
python main.py --max-pages 20 --max-depth 1

# demonstrate the depth limit
python main.py --max-pages 40 --max-depth 3 --links-per-page 5

# add to the existing database instead of clearing it
python main.py --keep-db
```

### Inspecting the database

`query.py` reads `data/crawler.db` through Python's standard-library `sqlite3` module, so
no extra tool has to be installed:

```bash
python query.py                  # overview: counts, depth spread, domains, statuses
python query.py pages            # every stored page, one line each
python query.py links            # the 25 most-linked-to targets
python query.py schema           # CREATE TABLE statements
python query.py "SELECT url, title FROM pages WHERE depth = 1 LIMIT 10"
```

If the `sqlite3` command-line tool *is* installed, the same queries work directly:

```bash
sqlite3 data/crawler.db "SELECT depth, COUNT(*) FROM pages GROUP BY depth;"
sqlite3 data/crawler.db "SELECT url, title FROM pages LIMIT 10;"
```

It ships with macOS and most Linux distributions but **not** with Windows — see the
database guide in §11 for how to install it or use a GUI instead.

---

## 10. Error handling

Per Task 3, the crawler never stops because of one bad page. It handles and **counts**:

| Situation | Handling |
|---|---|
| `200 OK` | parsed and stored |
| `404`, `403`, `500`, any non-200 | counted in `by_status` and `failure_reasons`, not stored |
| `requests.Timeout` | counted as `Timeout`, crawl continues |
| `requests.ConnectionError` | counted as `ConnectionError`, crawl continues |
| any other `RequestException` | counted by exception name, crawl continues |
| non-HTML response | skipped before parsing |
| `Ctrl+C` | partial statistics printed, database closed cleanly |

The recorded run shows `Failed Requests : 0` — the Guardian returned 200 for every URL the
filter allowed through. The handling paths are still in place and were exercised during
development against Reuters, which answers 401.

`robots.txt` is fetched once per host and cached. If it cannot be retrieved, the host is
treated as permissive — the standard interpretation, and the same behaviour as a missing
`robots.txt`.

One Windows-specific fix is applied in `main.py`: stdout is reconfigured to UTF-8, because
headlines containing curly quotes raise `UnicodeEncodeError` under the default cp1252
console encoding and would otherwise terminate the crawl mid-run.

---

## 11. Working with the SQLite database

`data/crawler.db` is a single self-contained file. `reader.py` is the interface to use
from code; `query.py` is for quick looks from the shell.

### `reader.py` — the read-only API

`database.Database` writes during a crawl. `reader.CrawlReader` is its counterpart for
everything afterwards, and is what the indexing assignment should build on.

```python
from reader import CrawlReader

with CrawlReader() as db:
    print(db.count_pages(), db.count_links())
    print(db.pages_per_depth())              # {0: 2, 1: 98}

    for page in db.pages(depth=1, limit=10): # listings omit `content`
        print(page.title)

    article = db.page(318, with_content=True)
    print(article.content_length, article.content[:300])

    for page in db.iter_pages(batch_size=25):  # streams the whole corpus
        index(page.content)
```

Two decisions in it are worth knowing about:

**The connection is read-only.** It opens the file through the `file:…?mode=ro` URI, so a
`DELETE` or `UPDATE` raises `sqlite3.OperationalError: attempt to write a readonly
database`. A crawl takes two minutes to collect; nothing that merely reads it should be
able to destroy it.

**Listings do not select `content`.** Content averages 6.8 KB per row, so `SELECT *` over
100 pages moves ~680 KB just to list titles. `pages()` returns `Page` objects whose
`content` is `None` until you ask via `with_content=True`, `page(id, with_content=True)`
or `iter_pages()`. `content=None` means *not loaded*; `content=""` would mean the page
genuinely had no text — the two are distinguishable, which `has_content` relies on.

`iter_pages()` batches with `fetchmany()` rather than materialising the corpus, so it
still works when the crawl is 10 000 pages rather than 100.

| Method | Returns |
|---|---|
| `count_pages()`, `count_links()`, `is_empty()` | counts |
| `page(id)`, `page_by_url(url)` | one `Page`, or `None` |
| `pages(depth=, domain=, status_code=, limit=, offset=)` | list of `Page` |
| `iter_pages(batch_size=)` | generator over the whole corpus |
| `search(term, in_content=False)` | pages matching a term |
| `pages_per_depth/domain/status()` | `{key: count}` |
| `content_stats()` | min / avg / max length, truncation count |
| `outbound_links(url)`, `inbound_links(url)` | the web graph |
| `top_targets(limit, crawled_only=)` | `(url, count)` pairs |
| `tables()`, `schema()`, `columns(table)` | structure |
| `sql(query, params)` | arbitrary read query as dicts |

Every filter and search term is passed as a **bound parameter**, never formatted into the
SQL string, so a term containing a quote is matched literally rather than changing the
query. Writes are blocked by the connection itself, not by inspecting query text — there
is no string pattern to work around.

Run `python reader.py` for a demonstration of the main methods against the live database.

### Option A — `query.py` (nothing to install)

Python bundles the `sqlite3` module, so this works out of the box:

```bash
python query.py                  # overview
python query.py pages            # stored pages
python query.py links            # most-linked-to targets
python query.py schema           # table definitions
python query.py "SELECT ..."     # any SQL
```

Sample overview from the recorded run:

```
Pages stored          : 100
Links recorded        : 13955
Distinct link targets : 2517

Pages per depth:
  depth 0: 2
  depth 1: 98

Content length (chars): min 469, avg 6746, max 20000
```

### Option B — the `sqlite3` command-line tool

Ships with macOS and most Linux distributions. **Windows does not include it.** To install:

```powershell
winget install SQLite.SQLite
```

Or download the *Precompiled Binaries for Windows* "command-line tools" bundle from
<https://sqlite.org/download.html>, unzip it, and add the folder to `PATH`.

Then:

```bash
sqlite3 data/crawler.db          # interactive shell
```

Useful shell commands (the dot-commands are `sqlite3`-specific, not SQL):

```
.tables                  list tables
.schema pages            show one table's definition
.headers on              print column names
.mode column             align output in columns
.quit                    exit
```

### Option C — a GUI

- **DB Browser for SQLite** — <https://sqlitebrowser.org> (`winget install DBBrowserForSQLite`)
- **VS Code** — the *SQLite Viewer* extension opens `.db` files in a tab

### Queries for the report

```sql
-- pages per depth (Task 6 evidence)
SELECT depth, COUNT(*) FROM pages GROUP BY depth ORDER BY depth;

-- pages per domain (focused-crawl evidence)
SELECT domain, COUNT(*) FROM pages GROUP BY domain;

-- HTTP status spread (Task 3 evidence)
SELECT status_code, COUNT(*) FROM pages GROUP BY status_code;

-- confirm no duplicate URLs were stored (Task 7 evidence)
SELECT COUNT(*) - COUNT(DISTINCT url) AS duplicates FROM pages;

-- the ten most-linked-to pages (the web graph in `links`)
SELECT target_url, COUNT(*) AS n FROM links
GROUP BY target_url ORDER BY n DESC LIMIT 10;

-- how many links each crawled page contributed
SELECT source_url, COUNT(*) AS outbound FROM links
GROUP BY source_url ORDER BY outbound DESC LIMIT 10;

-- read one stored article
SELECT title, SUBSTR(content, 1, 400) FROM pages WHERE id = 3;
```

### Reading the `links` table

The most-linked-to targets are all site navigation — `/world`, `/sport/tennis`,
`/tone/letters` and so on appear exactly 100 times each, once per crawled page. That is
the expected shape for a news site: every article carries the full section menu. The
interesting edges are the long tail below those, which are article-to-article links.

Note that `links` stores **every** discovered link, including ones the URL filter
rejected. So `/video` appears as a link target even though no `/video` page was ever
crawled — the edge is recorded, the page was not fetched. This is deliberate, and
explained in §6.

### Starting over

`python main.py` clears both tables before each run, so the database always reflects the
most recent crawl. To keep earlier results, pass `--keep-db`; to start completely fresh,
delete `data/crawler.db` and it will be recreated.
