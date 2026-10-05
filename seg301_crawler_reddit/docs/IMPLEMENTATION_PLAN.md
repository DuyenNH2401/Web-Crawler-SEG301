### Goal
Build a small Python CLI that reads recent subreddit posts and their comments into SQLite, with OAuth, public JSON and local browser-session adapters plus offline JSONL ingestion.

### Assumptions
- Subreddit is supplied at runtime; require `--max-comments` as a total per-run limit and expose `--max-posts` (default 100).
- User has no API access and uses data for research: primary path is authorized RFR/BigQuery export mapped into documented JSONL. RFR does not use PRAW.
- Keep an optional PRAW adapter for an explicitly approved Data API use case, using environment variables.
- Add `crawl-public` following the user's request to try collection without credentials; use descriptive headers, paced requests and bounded retries. HTTP accessibility does not confer approval; explain Reddit's policy and stop on access errors.
- Single process, no scheduler or web UI; include replies and preserve parent IDs.
- Store the user-requested 11 fields, including author identifiers when supplied; missing optional fields become NULL. Preserve prefixed post IDs and full comment URLs. Keep content for at most 48 hours by default; support refresh and purge.

### Plan
1. Define persistence and crawl behavior with tests.
   - Files: `tests/test_crawler.py`, `tests/test_public.py`
   - Change: Cover idempotency, parent relationships, deleted content, retention, bounded subreddit iteration, and dry run.
   - Verify: `python3 -m unittest discover -s tests -v` (initially fails before implementation).
2. Implement the crawler and SQLite store.
   - Files: `reddit_crawler.py`, `requirements.txt`, `.env.example`, `.gitignore`, `examples/comments.jsonl`
   - Change: Add crawl, crawl-public, import, sync, purge and stats commands; explicit timeouts, bounded retries and API rate-limit handling; synthetic demo usable without dependencies.
   - Verify: `python3 -m unittest discover -s tests -v`; `python3 reddit_crawler.py --help`.
3. Document and review the runnable result.
   - Files: `README.md`
   - Change: Add Vietnamese setup, CLI examples, limitations, and Reddit access/retention requirements.
   - Verify: Attempt dependency install in `.venv`; run offline tests and CLI smoke checks using temporary databases; inspect secrets and generated artifacts. The environment lacks ensurepip and DNS access to PyPI, so live dependency/API verification is external.

### Risks & mitigations
- API credentials/approval are external requirements: test offline and clearly distinguish live verification.
- API listings and comment expansion are bounded: report skipped branches; never promise complete historical coverage.
- SQLite writes: use parameterized statements, transactions and a unique comment ID.
- Deleted content: sync saved IDs and purge old rows. Users must schedule purge/sync for continuously retained data.

### Rollback plan
Delete the new Python/docs/config files and generated virtualenv. Back up any SQLite file before deleting it; no external writes are performed by the crawler.

### Verification results
- `python3 -W error::ResourceWarning -m unittest discover -s tests -v`: 60 offline tests cover requested schema/nulls, author mapping/clearing, legacy migration, public/session JSON collection, cookie host/HTTPS restrictions and secret-free errors, request-start logging, periodic crawl progress during blocked transport, progress worker cleanup, classified network failures and read-only DNS/proxy diagnostics without leaking proxy credentials.
- `python3 -m compileall -q reddit_crawler.py tests`: passed.
- CLI smoke checks with temporary SQLite files: total limit, repeated upsert, parent IDs, existing/new database dry run, stats, invalid/missing arguments, and missing credentials passed.
- Manual review: no Blocker/Major findings remaining in offline behavior. Live PRAW installation/integration remains unverified because PyPI DNS access fails and no approved credentials are available.
- No real Reddit data was fetched; sample records are synthetic. No external writes, deployment, or commits were performed.

### Read-only comment display
- Add `show --limit N` (default 10) in `reddit_crawler.py`, reading SQLite in read-only mode without migration/purge or network access. Support current and legacy schemas; newest collection first.
- Print numbered comment content, one physical line per record; escape embedded line breaks and display missing content as `None`.
- Document commands in `README.md`. Verify with CLI smoke checks using temporary current/legacy/empty/missing databases, invalid limits, byte preservation, then the existing offline suite and compilation.
- Rollback: remove the show command/helper; database schema and contents remain compatible.
- Verified: temporary-database CLI smoke checks passed for row limits/order, multiline/None output, invalid limits, empty/missing/unknown databases, legacy compatibility and unchanged database bytes. All 60 existing offline tests and Python compilation passed.
