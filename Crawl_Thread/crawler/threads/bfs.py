"""Search seeds (depth 0) -> relevant posts (1) -> reply pages (2, 3, ...)."""

import logging
from contextlib import closing
from dataclasses import asdict
from pathlib import Path

from crawler.common.frontier import Frontier
from crawler.common.models import Comment, ParsedThread
from crawler.common.normalize import matched_keywords
from crawler.common.storage import DatasetStore
from crawler.threads.collector import Collector
from crawler.threads.search import canonical_search_url, search_url
from parsers.threads import ParseError, ThreadsParser, canonical_post_url

LOGGER = logging.getLogger(__name__)


class BFSCrawler:
    def __init__(
        self,
        store: DatasetStore,
        collector: Collector,
        manifest: dict,
        options: dict,
        resume: bool = False,
        parser: ThreadsParser | None = None,
        retry_errors: bool = False,
    ):
        self.store, self.collector, self.manifest = store, collector, manifest
        self.parser = parser or ThreadsParser()
        self.frontier = Frontier(store.connection, manifest["run_id"], options, resume)
        if retry_errors:
            self.frontier.retry_errors()
        # Seeds/vocabulary are retained on resume; current budgets can be raised.
        self.options = {
            **self.frontier.options,
            **{
                k: options[k]
                for k in (
                    "post_limit",
                    "comment_limit",
                    "max_depth",
                    "max_pages",
                    "scroll_limit",
                )
            },
        }
        self.seeds = set(self.frontier.options.get("urls", []))

    def _seed(self):
        for keyword in self.frontier.options["queries"]:
            self.frontier.enqueue(search_url(keyword), "search", 0)
        for url in self.frontier.options.get("search_urls", []):
            self.frontier.enqueue(url, "search", 0)
        for url in self.frontier.options.get("urls", []):
            if self.frontier.count("post") >= self.options["post_limit"]:
                break
            self.frontier.enqueue(url, "post", 1, root_url=url)

    def _relevant(self, text: str) -> bool:
        return bool(
            matched_keywords(text, self.frontier.options["keywords"])
        ) and not matched_keywords(text, self.frontier.options["negatives"])

    def _snapshots(self, job):
        cached = self.frontier.pages(job.url)
        if cached is not None:
            paths, error = cached
            for path in paths:
                yield Path(path).read_text(encoding="utf-8"), path
            if error:
                raise RuntimeError(error)
            return
        paths = []
        self.frontier.cache(job.url, paths, completed=False)
        try:
            with closing(
                self.collector.pages(job.url, self.options["scroll_limit"])
            ) as pages:
                for html in pages:
                    path = str(self.store.snapshot(html, job.kind).resolve())
                    paths.append(path)
                    self.frontier.cache(job.url, paths, completed=False)
                    self.manifest["sources"].append(
                        {"url": job.url, "depth": job.depth, "snapshot": path}
                    )
                    yield html, path
        except GeneratorExit:
            self.frontier.cache(job.url, paths)
            raise
        except Exception as exc:
            self.frontier.cache(job.url, paths, str(exc))
            raise
        else:
            self.frontier.cache(job.url, paths)

    def _search(self, job):
        valid = False
        last_error = None
        page_ids = set()
        limited = False
        for html, path in self._snapshots(job):
            try:
                result = self.parser.parse_search(html)
            except ParseError as exc:
                # Allow initial browser snapshots to finish loading.
                if self.collector.render:
                    last_error = exc
                    continue
                raise
            valid = True
            limited = limited or result.login_limited
            for post in result.posts:
                page_ids.add(post.post_id)
                post.source_html = path
                self.frontier.candidate(post)
                if self.frontier.count("post") >= self.options["post_limit"]:
                    continue
                if self._relevant(post.content):
                    self.frontier.enqueue(
                        post.post_url,
                        "post",
                        job.depth + 1,
                        root_url=post.post_url,
                        discovered_from=job.url,
                    )
        if not valid:
            raise last_error or ParseError(
                "Search never reached a loaded results or empty-results state."
            )
        if limited:
            warning = f"AUTH_LIMITED: signed-out search results are partial: {job.url}. Use main.py login."
            self.manifest["warnings"].append(warning)
            LOGGER.warning(warning)
        LOGGER.info(
            "Search completed: %s unique candidates; %s post jobs queued",
            len(page_ids),
            self.frontier.count("post"),
        )
        if not page_ids:
            LOGGER.info(
                "No results displayed for %s; continuing with other BFS jobs.", job.url
            )

    def _thread(self, job):
        root_id = job.root_url.rsplit("/", 1)[-1]
        if self.store.comment_count(root_id) >= self.options["comment_limit"]:
            self.frontier.mark(job, "skipped")
            return
        parsed_any = False
        for html, path in self._snapshots(job):
            try:
                parsed = self.parser.parse(html, job.url, path)
            except ParseError:
                if self.collector.render:
                    continue
                raise
            parsed_any = True
            if job.kind == "post":
                if job.url not in self.seeds and not self._relevant(
                    parsed.post.content
                ):
                    self.frontier.mark(job, "skipped")
                    self.manifest["warnings"].append(
                        f"Rejected irrelevant post: {job.url}"
                    )
                    return
                root = parsed.post
                comments = parsed.comments
            else:
                root = self.store.get_post(root_id)
                if root is None:
                    raise ParseError("Reply branch has no stored root post.")
                # The opened comment remains a comment under the original root.
                record = asdict(parsed.post)
                own_comment = Comment(
                    comment_id=record.pop("post_id"),
                    comment_url=record.pop("post_url"),
                    post_id=root_id,
                    **record,
                )
                comments = (
                    [own_comment] if own_comment.content else []
                ) + parsed.comments
                for comment in comments:
                    comment.post_id = root_id
            known = self.store.comment_ids(root_id)
            allowed = []
            for comment in comments:
                if comment.comment_id == root_id:
                    continue
                if comment.comment_id not in known:
                    if len(known) >= self.options["comment_limit"]:
                        continue
                    known.add(comment.comment_id)
                allowed.append(comment)
            self.store.save(ParsedThread(root, allowed, parsed.warnings))
            self.manifest["warnings"].extend(parsed.warnings)
            for comment in allowed:
                if (
                    comment.comment_url == job.url
                    or comment.comment_url == job.root_url
                ):
                    continue
                self.frontier.enqueue(
                    comment.comment_url, "reply", job.depth + 1, job.root_url, job.url
                )
            if len(known) >= self.options["comment_limit"]:
                self.manifest["warnings"].append(
                    f"Comment limit reached for {root_id}."
                )
                break
        if not parsed_any:
            raise ParseError("Page never exposed a rendered post card.")

    def run(self) -> dict:
        self._seed()
        reason = "frontier_exhausted"
        while job := self.frontier.peek():
            if job.depth > self.options["max_depth"]:
                reason = "max_depth"
                self.manifest["warnings"].append(
                    "Reply traversal reached max_depth; deeper jobs remain pending."
                )
                break
            if (
                not self.frontier.was_attempted(job.url)
                and self.frontier.fetched_count() >= self.options["max_pages"]
            ):
                reason = "max_pages"
                break
            self.frontier.mark(job, "processing")
            LOGGER.info("BFS depth=%s kind=%s url=%s", job.depth, job.kind, job.url)
            try:
                if job.kind == "search":
                    self._search(job)
                else:
                    self._thread(job)
                row = self.store.connection.execute(
                    "SELECT status FROM bfs_frontier WHERE id=?", (job.id,)
                ).fetchone()
                if row[0] == "processing":
                    self.frontier.mark(job, "done")
            except Exception as exc:  # noqa: BLE001 -- URL errors are recorded without terminating other BFS branches
                self.frontier.mark(job, "error", str(exc))
                self.manifest["errors"].append(
                    {
                        "url": job.url,
                        "depth": job.depth,
                        "kind": job.kind,
                        "message": str(exc),
                    }
                )
                LOGGER.error("BFS failed %s: %s", job.url, exc)
        return self.finish(reason)

    def finish(self, reason: str) -> dict:
        """Report persistent state, including after a user interrupts the crawl."""
        self.manifest["bfs"] = {**self.frontier.stats(), "stop_reason": reason}
        self.manifest["errors"] = [
            {"url": url, "depth": depth, "kind": kind, "message": error}
            for url, depth, kind, error in self.store.connection.execute(
                "SELECT url,depth,kind,error FROM bfs_frontier WHERE session=? AND status='error'",
                (self.frontier.session,),
            )
        ]
        self.manifest["keywords"] = self.frontier.options["keywords"]
        self.manifest["negative_keywords"] = self.frontier.options["negatives"]
        self.manifest["search_queries"] = self.frontier.options["queries"]
        self.manifest["seeds"] = [
            search_url(q) for q in self.frontier.options["queries"]
        ] + self.frontier.options.get("search_urls", [])
        self.manifest["limits"] = self.options
        self.manifest["posts_crawled"] = self.store.connection.execute(
            "SELECT count(DISTINCT f.url) FROM bfs_frontier f JOIN posts p ON p.post_url=f.url "
            "WHERE f.session=? AND f.kind='post'",
            (self.frontier.session,),
        ).fetchone()[0]
        self.manifest["comments_found"] = self.store.connection.execute(
            "SELECT count(*) FROM comments WHERE post_id IN (SELECT p.post_id FROM posts p "
            "JOIN bfs_frontier f ON f.url=p.post_url WHERE f.session=? AND f.kind='post')",
            (self.frontier.session,),
        ).fetchone()[0]
        return self.frontier.candidates()


def crawl_options(args, keywords: list[str], negatives: list[str]) -> dict:
    urls = []
    for url in args.url or []:
        canonical = canonical_post_url(url)
        if not canonical:
            raise ValueError(f"Invalid Threads post URL: {url}")
        urls.append(canonical)
    search_urls = []
    for url in args.seed_url or []:
        canonical = canonical_search_url(url)
        if canonical is None:
            raise ValueError(f"Seed must be a Threads keyword search URL: {url}")
        search_urls.append(canonical)
    queries = args.keyword or ([] if urls or search_urls else keywords)
    return {
        "queries": list(dict.fromkeys(queries)),
        "search_urls": search_urls,
        "urls": list(dict.fromkeys(urls)),
        "keywords": list(
            dict.fromkeys(
                keywords
                + queries
                + [canonical_search_url(u, keyword_only=True) for u in search_urls]
            )
        ),
        "negatives": negatives,
        "post_limit": args.post_limit,
        "comment_limit": args.comment_limit,
        "scroll_limit": args.scroll_limit,
        "max_depth": args.max_depth,
        "max_pages": args.max_pages,
    }
