# Threads regional discrimination crawler

Extract authored Vietnamese text from saved/rendered Threads pages. The parser is
verified against the two actual HTML files in `sample_pages`, including the
comment beginning “Nhiều thằng hà nội…”. It preserves original spelling, accents,
slang, punctuation and emoji. Whitespace from the formatted HTML is collapsed;
separate text paragraphs remain separate. UI labels and counters are excluded.

## Run with your existing venv

From this project directory. In CMD (with your venv active), use **double quotes**:

```cmd
python main.py samples
python -m pytest -q
```

In PowerShell:

```powershell
& 'C:\Users\ADMIN\ai_venv\Scripts\python.exe' main.py samples
& 'C:\Users\ADMIN\ai_venv\Scripts\python.exe' -m pytest -q
```

If dependencies are missing:

```powershell
& 'C:\Users\ADMIN\ai_venv\Scripts\python.exe' -m pip install -r requirements.txt
```

The supplied samples produce **1 post, 11 comments, and 15 unique search
candidates**. Search candidates are kept separately from the post/comment
dataset. The post's displayed reply count is 208; the saved file contains only
11 loaded comments. Those 11 are not a complete thread.

Outputs:

| Path | Contents |
| --- | --- |
| `data/exports/posts.jsonl` and `posts.csv` | Collected parent posts |
| `data/exports/comments.jsonl` and `comments.csv` | Authored comments/replies |
| `data/exports/candidates.jsonl` | Search candidates and matched topic keywords |
| `data/dataset.sqlite3` | Persistent local dataset, deduplicated on reruns |
| `data/raw_html/` | Snapshots named with SHA-256 content digests |
| `data/runs/` | Run inputs, keywords, limits, errors and coverage notes |

JSONL uses UTF-8; CSV uses UTF-8 with a BOM for Excel. `content` is the text column
to use for NLP. `source_html` connects each record to its snapshot. In offline
mode, `collected_at` means the time the file was parsed, not the original download
time. Use `--output another_directory` to create a separate dataset.

Parse another downloaded post, or discover URLs from a saved search:

```powershell
& 'C:\Users\ADMIN\ai_venv\Scripts\python.exe' main.py parse --html 'post.html'
& 'C:\Users\ADMIN\ai_venv\Scripts\python.exe' main.py parse --html 'page.html' --post-url 'https://www.threads.com/@username/post/SHORTCODE'
& 'C:\Users\ADMIN\ai_venv\Scripts\python.exe' main.py discover --html 'search.html'
& 'C:\Users\ADMIN\ai_venv\Scripts\python.exe' main.py export
```

`--html` can be repeated. Browser “Save page as” files retain the original URL in
an HTML comment. For `page.content()` snapshots, supply `--post-url` if metadata
does not contain a post URL. A homepage canonical URL is never used as the post ID.

## Automatic BFS collection

The live crawler uses a persistent breadth-first queue:

```text
Depth 0: all keyword search URLs
Depth 1: relevant post URLs found in those searches
Depth 2: comment permalinks found in those posts
Depth 3+: newly discovered replies, retaining the original root post
```

All depth-0 seeds are processed before any depth-1 posts, and all depth-1 posts
before depth-2 reply pages. The graph follows post/comment permalinks within the
parsed search/thread sections; profile, media and neighboring feed links are
excluded. Each URL is fetched once per crawl session, even when it belongs to
multiple root contexts. Raw snapshots are reused for those additional contexts.
Duplicate links and cycles cannot keep the crawler running indefinitely.

Browser rendering is now the default. Install it once:

```powershell
& 'C:\Users\ADMIN\ai_venv\Scripts\python.exe' -m pip install -r requirements.txt
& 'C:\Users\ADMIN\ai_venv\Scripts\python.exe' -m playwright install chromium
```

Run using all keywords from `config/keywords.yaml`; no hand-selected post URLs or
`--render` flag are needed:

```powershell
& 'C:\Users\ADMIN\ai_venv\Scripts\python.exe' main.py crawl --output 'data/regional_discrimination'
```

Override the search seeds with keywords or actual search URLs:

```powershell
& 'C:\Users\ADMIN\ai_venv\Scripts\python.exe' main.py crawl --keyword 'namkiki' --keyword 'parky' --max-depth 3 --max-pages 200 --output 'data/regional_discrimination'
& 'C:\Users\ADMIN\ai_venv\Scripts\python.exe' main.py crawl --seed-url 'https://www.threads.com/search?q=namkiki&serp_type=default'
```

`--keywords custom.yaml` supplies a different topic vocabulary. `--keyword` and
`--seed-url` replace the default search seeds, and their terms also participate
in relevance matching. Search candidates and fetched seed posts must match the
topic vocabulary; their comments/replies are collected regardless of their own
keyword matches. This preserves neutral and opposing comments. Explicit `--url`
seeds remain available for debugging and bypass topic rejection.

| Argument | Default | Bound |
| --- | --- | --- |
| `--post-limit` | 50 | Maximum root post jobs scheduled from search seeds |
| `--comment-limit` | 500 | Maximum stored comments per root, across reply branches |
| `--max-pages` | 200 | Unique page fetch attempts across the entire crawl session |
| `--max-depth` | 3 | Search=0, post=1, comment page=2, nested reply page=3 |
| `--scroll-limit` | 20 | Maximum scrolling steps for each fetched page |
| `--delay` | 1 | Request/scroll delay in seconds, minimum 1 |

These are ceilings, not promised dataset sizes. Breadth-first processing visits
all seed searches before posts; set `--max-pages` above your seed count to leave
room for post/reply pages. If the page/depth budget is reached, unvisited jobs
remain in the SQLite frontier. Resume and raise those budgets:

```powershell
& 'C:\Users\ADMIN\ai_venv\Scripts\python.exe' main.py crawl --resume --max-pages 400 --max-depth 4 --output 'data/regional_discrimination'
```

For an authenticated session, sign in through a normal browser window:

```cmd
python main.py login
```

Sign in manually in that window, then press Enter in the terminal. This saves
`browser_storage_state.json`; subsequent `crawl` commands load it automatically.
Use `--storage-state another_storage_state.json` to select a different saved session.
Login does not promise results for every keyword. If Threads displays “No results,”
that is now recorded as an empty search rather than a parser failure. Guest pages
with “Log in for more threads about this topic” are flagged as partial results.

To continue an existing queue from CMD:

```cmd
python main.py crawl --resume --retry-errors --max-pages 500 --max-depth 4 --output "data/regional_discrimination"
```

`--retry-errors` requires `--resume`: failed fetches are retried, while parser-only
failures can reuse saved HTML. Already-completed searches retain their cached
results; start a fresh crawl without `--resume` to repeat all searches after login.

`--resume` uses the latest session in that output directory and retains its seeds
and vocabulary. It resumes pending/interrupted work; completed and failed jobs
remain recorded. A fresh `crawl` without `--resume` starts a new frontier while
keeping the accumulated dataset. Use a different output directory for an entirely
separate dataset. Ctrl+C waits for the current browser operation to settle (at most its 30-second timeout), then exports collected data and preserves the frontier;
interrupted in-flight pages are fetched again on resume because their cached
snapshots may be incomplete.

Progress logs report each node's depth, kind and URL. The final manifest records
queue statuses, unique pages attempted, stop reason, snapshots, errors and limits.
Exports happen automatically in `<output>/exports/`. The durable graph and cache
are in `bfs_sessions`, `bfs_frontier`, `bfs_pages` and `bfs_candidates` within the
same SQLite database.

`--headed` shows the browser. `--storage-state private_storage_state.json` accepts
your own authorized Playwright session. `--http-only` opts into plain HTTP; it
cannot scroll and may return an unrendered shell. Authentication and crawl
permission are separate: login redirects, rate limits and access
challenges stop the affected job. No credentials are copied from the plan into
code. Keep session files private; the plan contains credentials and should not
be published as-is.

Reply branches are traversed by opening comment permalinks rather than asserting
that the first snapshot contains the whole thread. Each page's scrolling snapshots
are saved and merged. Hidden content without a usable permalink or content beyond
the configured limits can still be missed, so complete coverage is not claimed.
A BFS discovery edge records how a page was found; it does not prove the exact
parent comment of every record rendered on that page.

The parser is also verified against your October 5 guest-search snapshots:
actual empty results and actual login-limited results. Authenticated live crawling
still requires your own login session. Tests validate BFS order, shared branches,
cycles, limits, empty-result handling, interrupted cleanup/exports and resumes.
An actual local Chromium smoke test also passed readiness detection and deferred
Ctrl+C cleanup using local HTML; it did not access your login session.

If CMD previously created a folder with literal single quotes from the PowerShell
examples, `--output` now strips those accidental surrounding quotes. The existing
run was recovered into `data/regional_discrimination` without deleting the original.

## What the snapshots actually expose

| Field | Evidence / convention |
| --- | --- |
| Post/comment ID | Shortcode in the timestamp's `/@handle/post/SHORTCODE` link |
| Author name | Handle in that permalink |
| Author ID | `UNKNOWN`; a handle is not a numeric account ID |
| Timestamp | `time[datetime]`, normalized to UTC; `null` if unavailable |
| Likes | Like button's displayed count; `null` if absent |
| Rounded counts | e.g. `4.4K` → 4400, with `like_count_is_approximate=true` |
| Reply parent | `UNKNOWN`; the saved DOM does not prove an exact parent ID |
| Reply group | First permalink within the same `data-virtualized` container |
| Text completeness | `null` means unknown; detected inline clamps are flagged |

Reply groups preserve visible grouping, **not an asserted reply tree**. A group
with three cards does not prove whether the third replies to the first or second.
`ROOT` is reserved for a confirmed direct reply and is not assigned speculatively.
Do not substitute a collection time for a missing publication time, or zero for
an unavailable count.

Posts are deduplicated by `(platform, post_id)`. Comments use
`(platform, comment_id, post_id)` so the same Threads reply seen under different
collected parent contexts keeps both associations. Deduplicate by `comment_id`
when your analysis needs unique text records across contexts.

See `docs/selectors.md` for the fixture evidence. SQLite is the runnable first
storage implementation; PostgreSQL and Parquet from the larger plan are not
implemented. Crawling and NLP labeling remain separate.
