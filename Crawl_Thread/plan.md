# Multi-Platform Social Comment Crawler — Plan

## 1. Goal

Build a crawler that discovers **topic-relevant posts/threads**, collects their comments/replies, normalizes them into one common schema, and stores both normalized data and raw HTML snapshots for reproducibility.

Target platform:

- Threads

Main flow:

```text
Keyword / topic
      |
      v
Search / Discovery
      |
      v
Candidate post / thread URLs
      |
      v
Post metadata
      |
      v
Comments + replies
      |
      v
Normalization
      |
      +--------------------+
      |                    |
      v                    v
Normalized DB        Raw HTML snapshots
      |
      v
Deduplication / validation / export
```

---

## Current implementation — Threads BFS

The runnable Threads crawler now starts from keyword search URLs and uses a
persistent SQLite breadth-first frontier: search seeds at depth 0, relevant posts
at depth 1, comment permalinks at depth 2, and further reply pages at deeper levels.
URL fetches are cached per session; reply records retain the original root post.
The crawler has page/depth/post/comment/scroll limits, per-URL error recording,
raw snapshots, UTF-8 exports, and resume support for pending/interrupted work.
Browser rendering is the default. PostgreSQL and additional platforms remain
future work; exact reply parents and total coverage are not inferred from BFS edges.
See README.md for current commands and tests.

---

## 2. Repository structure

```text
comment-crawler/
│
├── plan.md
├── README.md
├── requirements.txt
├── .env.example
│
├── config/
│   ├── keywords.yaml
│   └── platforms.yaml
│
├── crawler/
│   ├── common/
│   │   ├── models.py
│   │   ├── normalize.py
│   │   ├── deduplicate.py
│   │   ├── rate_limit.py
│   │   └── storage.py
│   │
│   ├── youtube/
│   │   ├── search.py
│   │   ├── posts.py
│   │   └── comments.py
│   ├── tiktok/
│   │   ├── search.py
│   │   ├── posts.py
│   │   └── comments.py
│   ├── facebook/
│   │   ├── search.py
│   │   ├── posts.py
│   │   └── comments.py
│   ├── x/
│   │   ├── search.py
│   │   ├── posts.py
│   │   └── comments.py
│   ├── reddit/
│   │   ├── search.py
│   │   ├── posts.py
│   │   └── comments.py
│   └── threads/
│       ├── search.py
│       ├── posts.py
│       └── comments.py
│
├── parsers/
│   ├── youtube.py
│   ├── tiktok.py
│   ├── facebook.py
│   ├── x.py
│   ├── reddit.py
│   └── threads.py
│
├── fixtures/
│   ├── youtube/
│   ├── tiktok/
│   ├── facebook/
│   ├── x/
│   ├── reddit/
│   └── threads/
│
├── data/
│   ├── raw_html/
│   ├── normalized/
│   └── exports/
│
└── tests/
    ├── test_parsers.py
    ├── test_normalization.py
    └── test_deduplication.py
```

---

## 3. Database schema

Keep the first version intentionally small and platform-independent.

```sql
CREATE TABLE posts (
    id              BIGSERIAL PRIMARY KEY,
    platform        VARCHAR(20) NOT NULL,
    post_id         VARCHAR(255) NOT NULL,
    post_url        TEXT NOT NULL,
    content         TEXT NOT NULL,
    author_id       VARCHAR(255) NOT NULL,
    author_name     VARCHAR(255) NOT NULL,
    created_at      TIMESTAMP NOT NULL,
    collected_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(platform, post_id)
);

CREATE TABLE comments (
    id              BIGSERIAL PRIMARY KEY,

    platform        VARCHAR(20) NOT NULL,
    comment_id      VARCHAR(255) NOT NULL,
    content         TEXT NOT NULL,

    author_id       VARCHAR(255) NOT NULL,
    author_name     VARCHAR(255) NOT NULL,

    parent_id       VARCHAR(255) NOT NULL,
    post_id         VARCHAR(255) NOT NULL,
    comment_url     TEXT NOT NULL,

    created_at      TIMESTAMP NOT NULL,
    like_count      INTEGER NOT NULL DEFAULT 0,

    collected_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(platform, comment_id)
);
```

### Non-NULL conventions

Use:

```text
UNKNOWN
```

when author ID/name cannot be obtained.

Use:

```text
ROOT
```

when a comment has no parent.

Use:

```text
0
```

when like/upvote count is unavailable.

---

## 4. Why `posts` and `comments` are separate

Do not repeat post metadata in every comment.

```text
YouTube video A
 ├── comment 1
 ├── comment 2
 ├── comment 3
 └── comment 4
```

The video metadata is stored once in `posts`, while comments reference:

```text
post_id = video_A
```

This prevents duplication and makes later analysis easier.

---

## 5. Keyword / topic discovery module

This must remain a separate module.

### TODO: keyword research

Fill this section after deciding the project's actual topic vocabulary.

```yaml
topic:
  name: "regional discrimination (Phân biệt vùng miền)"

keywords:
  primary:
    - "so sánh bắc nam"
    - "namkiki"
    - "namkicho"
    - "backycho"
    - "parkyky"
    - "cá rô cây"
    - "gia trưởng"
    - "tiêu sài phung phí"


  platform_specific:
    threads:
      - ""
```

For example, a Threads search URL can look like:

```text
https://www.threads.com/search?q=namkiki&serp_type=default
```

The search page is a **discovery source**, not the final dataset.

Conceptually:

```text
keyword
   ↓
platform search
   ↓
search result posts
   ↓
extract post/thread URLs
   ↓
deduplicate URLs
   ↓
crawl individual posts
   ↓
crawl comments
```

Each platform gets its own search adapter because search URLs, pagination, rendering and access mechanisms differ.

---

## 6. Search/discovery interface

Every platform adapter should expose the same conceptual interface:

```python
class PlatformSearcher:
    def search(self, keyword: str, limit: int) -> list[str]:
        ...
```

Return candidate post/thread URLs, not comments.

Example:

```python
urls = searcher.search("namkiki", limit=50)
```

Then:

```python
for url in urls:
    post = crawler.fetch_post(url)
    comments = crawler.fetch_comments(url)
```

---

## 7. Search relevance filtering

Keyword matching alone is not enough.

Use three stages:

### Stage A — search relevance

Search using:

```text
primary keywords
synonyms
related terms
```

### Stage B — post relevance

Check title/caption/text against the topic vocabulary:

```python
is_relevant(post.content, keywords)
```

Start with:

```text
case-insensitive exact matching
+
simple normalization
```

Later, optionally add:

```text
TF-IDF
embedding similarity
classifier
```

### Stage C — comment collection

Only crawl comments after the parent post passes the relevance filter.

This avoids spending requests on unrelated posts.

---

## 8. Platform adapter design

Each platform should provide:

```text
Search
  ↓
Fetch post
  ↓
Parse post
  ↓
Fetch comments
  ↓
Parse comments
```

Use separate adapters:

```text
YouTubeAdapter
TikTokAdapter
FacebookAdapter
XAdapter
RedditAdapter
ThreadsAdapter
```

Do not create one huge parser containing a giant `if platform == ...` chain.

---

## 9. HTML collection strategy

The files in `fixtures/` are **parser test inputs**.

For each platform:

```text
real page
   ↓
save HTML snapshot
   ↓
fixtures/<platform>/*.html
   ↓
write parser
   ↓
unit test parser
```

This matters because social-media DOM structures can change.

Do not rely on a selector that has never been tested against saved HTML.

---

## 10. HTML fixture requirements

Each fixture should contain enough structure to test:

1. post ID
2. post URL
3. post content
4. author ID
5. author name
6. post timestamp
7. comment ID
8. comment content
9. comment author
10. comment timestamp
11. parent comment ID
12. like/upvote count
13. reply relationship

Example **synthetic** fixture:

```html
<article data-post-id="post-001">
    <a data-author-id="user-001"
       href="/user/example">
        Example User
    </a>

    <div data-post-content>
        Example post content.
    </div>

    <time datetime="2026-10-05T09:00:00Z">
        2026-10-05T09:00:00Z
    </time>

    <div data-comment-id="comment-001"
         data-parent-id="ROOT">

        <a data-comment-author-id="user-002">
            Commenter
        </a>

        <div data-comment-content>
            Example comment.
        </div>

        <time datetime="2026-10-05T09:10:00Z">
            2026-10-05T09:10:00Z
        </time>

        <span data-like-count="5">
            5
        </span>
    </div>
</article>
```

**Important:** these `data-*` attributes are deliberately synthetic. They are NOT claims about the live platform DOM.

For real parsing, first save an actual permitted page snapshot, inspect its DOM/embedded data, and then document the actual selectors or JSON paths.

---

## 11. Parser selector priority

Prefer, in this order:

```text
1. Stable semantic attributes / structured data
2. Embedded JSON state
3. Accessible attributes / semantic HTML
4. Stable URL patterns
5. CSS classes as a last resort
```

Avoid brittle selectors such as:

```css
div.css-1abcxyz > div.css-9xyz123
```

when a stable identifier exists.

---

## 12. Embedded JSON / hydration state

Modern social sites may render content with JavaScript.

Inspect:

```text
HTML
├── visible DOM
├── <script type="application/ld+json">
├── embedded JSON
├── hydration state
└── links / metadata
```

Recommended order:

```python
HTML
  ↓
BeautifulSoup / lxml
  ↓
JSON-LD
  ↓
embedded JSON state
  ↓
semantic HTML
  ↓
fallback CSS selectors
```

---

## 13. Browser automation

Use browser automation only when ordinary HTTP retrieval is insufficient.

Recommended stack:

```text
Python
├── Playwright
├── httpx
├── BeautifulSoup / lxml
└── PostgreSQL
```

Strategy:

```text
HTTP request
    ↓
Can required data be parsed?
    ├── YES → HTTP parser
    └── NO
         ↓
     Playwright
         ↓
     rendered HTML
         ↓
       parser
```

Do not attempt to bypass authentication, CAPTCHA, access controls, robots restrictions, or other platform security mechanisms. If authentication is required, document it as a project constraint.

---

## 14. Pagination / infinite scrolling

Possible mechanisms:

```text
page number
cursor
load more
infinite scroll
continuation token
```

Implement platform-specific pagination with a hard limit.

For infinite scroll:

```text
load page
   ↓
extract current items
   ↓
scroll
   ↓
wait
   ↓
extract newly loaded items
   ↓
deduplicate
   ↓
repeat until limit
```

Never allow an unbounded crawl.

---

## 15. Comment threading

Represent comment hierarchy using:

```text
parent_id
```

Example:

```text
ROOT
├── C001
│   ├── C002
│   └── C003
└── C004
```

Database:

```text
C001 parent_id = ROOT
C002 parent_id = C001
C003 parent_id = C001
C004 parent_id = ROOT
```

Do not flatten replies into the comment text.

---

## 16. Normalization

All platform-specific records become one common model before storage.

```python
@dataclass
class NormalizedComment:
    platform: str
    comment_id: str
    content: str
    author_id: str
    author_name: str
    parent_id: str
    post_id: str
    comment_url: str
    created_at: datetime
    like_count: int
    collected_at: datetime
```

Pipeline:

```text
Platform HTML
    ↓
PlatformParser
    ↓
NormalizedComment
    ↓
Validator
    ↓
Database
```

---

## 17. Deduplication

Comments:

```text
(platform, comment_id)
```

must be unique.

Posts:

```text
(platform, post_id)
```

must be unique.

During discovery, also deduplicate URLs:

```python
seen_urls = set()
```

This prevents the same post from being crawled repeatedly when several keywords find it.

---

## 18. Crawl metadata

Recommended table:

```sql
CREATE TABLE crawl_runs (
    id              BIGSERIAL PRIMARY KEY,
    platform        VARCHAR(20) NOT NULL,
    keyword         TEXT NOT NULL,
    started_at      TIMESTAMP NOT NULL,
    finished_at     TIMESTAMP NOT NULL,
    posts_found     INTEGER NOT NULL DEFAULT 0,
    posts_crawled   INTEGER NOT NULL DEFAULT 0,
    comments_found  INTEGER NOT NULL DEFAULT 0,
    errors          INTEGER NOT NULL DEFAULT 0
);
```

This lets the dataset answer:

```text
What keyword produced this data?
When was it crawled?
Which platform?
How many posts?
How many comments?
```

---

## 19. Raw HTML storage

Save raw page snapshots under:

```text
data/raw_html/
    youtube/
    tiktok/
    facebook/
    x/
    reddit/
    threads/
```

Example:

```text
threads_post_123456_2026-10-05T10-00-00.html
```

Why?

```text
parser bug
   ↓
rerun parser
   ↓
without crawling the platform again
```

This is useful for debugging and reproducibility.

---

## 20. Fixture-driven parser development

For every platform:

### Step 1

Collect a small number of legitimate page snapshots where permitted.

### Step 2

Put them into:

```text
fixtures/<platform>/
```

### Step 3

Inspect the HTML and embedded JSON.

### Step 4

Document the actual selectors / JSON paths.

Example:

```yaml
platform: threads

post:
  id: "<actual selector or JSON path>"
  content: "<actual selector or JSON path>"
  author_id: "<actual selector or JSON path>"
  author_name: "<actual selector or JSON path>"

comment:
  id: "<actual selector or JSON path>"
  content: "<actual selector or JSON path>"
  author_id: "<actual selector or JSON path>"
  parent_id: "<actual selector or JSON path>"
  created_at: "<actual selector or JSON path>"
  like_count: "<actual selector or JSON path>"
```

### Step 5

Write unit tests.

```python
def test_threads_parser():
    html = load_fixture("threads/post.html")

    post, comments = ThreadsParser().parse(html)

    assert post.post_id != "UNKNOWN"
    assert len(comments) > 0
    assert comments[0].content != ""
```

---

## 21. Search configuration

Example CLI:

```bash
python main.py \
    --platform threads \
    --keyword "namkiki" \
    --post-limit 50 \
    --comment-limit 500
```

Multiple keywords:

```bash
python main.py \
    --platform threads \
    --keywords config/keywords.yaml
```

All platforms:

```bash
python main.py \
    --platform all \
    --keywords config/keywords.yaml
```

---

## 22. Recommended crawl pipeline

```text
CONFIG
  |
  | keywords
  v
DISCOVERY
  |
  | search(keyword)
  v
POST URL QUEUE
  |
  | deduplicate
  v
POST FETCHER
  |
  | HTML / rendered HTML
  v
POST PARSER
  |
  | relevant?
  +------ NO ------> discard
  |
 YES
  |
  v
COMMENT FETCHER
  |
  v
COMMENT PARSER
  |
  v
NORMALIZER
  |
  v
VALIDATOR
  |
  +---- invalid ----> error log
  |
 valid
  |
  v
DEDUPLICATOR
  |
  v
DATABASE
  |
  +----> normalized export
  |
  +----> raw HTML archive
```

---

## 23. Error handling

One broken post must not kill the entire crawl.

```python
try:
    crawl_post(url)
except Exception as exc:
    log_error(url, exc)
    continue
```

Record:

```text
platform
URL
keyword
error type
error message
timestamp
```

Categories:

```text
HTTP_ERROR
TIMEOUT
PARSER_ERROR
MISSING_FIELD
AUTH_REQUIRED
RATE_LIMITED
CONTENT_UNAVAILABLE
UNKNOWN
```

---

## 24. Rate limiting

Use platform-specific request delays and exponential backoff.

```text
request
 ↓
delay
 ↓
request
 ↓
delay
```

Never attempt to defeat a platform's rate limits.

---

## 25. Data validation

Before inserting a comment:

```python
assert platform != ""
assert comment_id != ""
assert content != ""
assert post_id != ""
assert author_id != ""
assert author_name != ""
assert parent_id != ""
assert comment_url != ""
assert like_count >= 0
```

Do not silently insert malformed records.

---

## 26. Export formats

Support:

```text
PostgreSQL
CSV
JSONL
Parquet
```

JSONL example:

```json
{"platform":"youtube","comment_id":"...","content":"..."}
{"platform":"reddit","comment_id":"...","content":"..."}
```

Parquet is preferable for very large datasets.

---

## 27. NLP-ready output

The crawler should initially stop at clean data.

```text
comments
   ↓
cleaning
   ↓
language detection
   ↓
tokenization
   ↓
sentiment / topic / toxicity / classification
```

Do not couple crawling to a particular NLP model.

---

## 28. Implementation phases

### Phase 1 — Schema + models

- [ ] Create PostgreSQL schema
- [ ] Create `Post` model
- [ ] Create `NormalizedComment`
- [ ] Create `crawl_runs`
- [ ] Implement database insertion
- [ ] Implement uniqueness constraints

### Phase 2 — Keyword discovery

- [ ] Create `keywords.yaml`
- [ ] Add project topic
- [ ] Add primary keywords
- [ ] Add synonyms
- [ ] Add related terms
- [ ] Add negative terms
- [ ] Add platform-specific terms
- [ ] Test search-result relevance

### Phase 3 — HTML fixtures

- [ ] Capture legitimate HTML snapshots where permitted
- [ ] Store one or more fixtures per platform
- [ ] Identify post fields
- [ ] Identify comment fields
- [ ] Identify reply relationships
- [ ] Document selectors / JSON paths

### Phase 4 — First parser

Implement one platform completely:

```text
search
→ post
→ comments
→ replies
→ normalization
→ database
```

Recommended first target:

```text
Reddit
```

because its discussion/thread model is comparatively straightforward.

### Phase 5 — Remaining platforms

- [ ] YouTube
- [ ] TikTok
- [ ] Facebook
- [ ] X
- [ ] Threads

Do not implement all six simultaneously.

### Phase 6 — Robustness

- [ ] Pagination
- [ ] retry/backoff
- [ ] rate limiting
- [ ] deduplication
- [ ] raw HTML snapshots
- [ ] parser tests
- [ ] crawl logs
- [ ] resume interrupted crawls

### Phase 7 — Dataset generation

- [ ] Run keyword searches
- [ ] Collect candidate posts
- [ ] Filter irrelevant posts
- [ ] Crawl comments
- [ ] Validate records
- [ ] Remove duplicates
- [ ] Export dataset
- [ ] Record crawl configuration

---

## 29. Definition of done

Given:

```text
a topic
+
a keyword list
+
a platform
```

the crawler can:

1. discover relevant posts
2. extract post URLs
3. fetch individual posts
4. extract comments
5. extract replies
6. preserve parent-child relationships
7. normalize all comments into one schema
8. remove duplicates
9. store crawl metadata
10. save raw HTML snapshots
11. export NLP-ready data

The parser must have automated fixture tests so that a future HTML/DOM change is detected instead of silently producing an empty or corrupted dataset.

## Additional info: In case you need, here are some cookies:
  - "sessionid": "68278488540%3AX2djztBPXyDcu7%3A28%3AAYlpB21zvMnSfJSGsUF2z-nIag0YocCXbqwOpbekqw"
  - "ds_user_id"; "68278488540"
  - "csrftoken": "VYxssqw2gzPwo4UbpP8jQGeUwhmSBc3T"