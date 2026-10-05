"""Exercise traversal order, cycles, shared branches, limits and durable resume."""

import argparse
import json
from html import escape
from pathlib import Path

import pytest

import main
from crawler.common.storage import DatasetStore
from crawler.threads.bfs import BFSCrawler
from crawler.threads.search import canonical_search_url, search_url


def url(code):
    return f"https://www.threads.com/@user/post/{code}"


def card(code, text):
    return f'''<div data-pressable-container="true">
        <a href="{url(code)}"><time datetime="2026-10-05T00:00:00Z">today</time></a>
        <span dir="auto" style="--x---base-line-clamp-line-height: 1.4em">
            <span>{escape(text)}</span>
        </span></div>'''


def search(*codes):
    return (
        '<div data-pagelet="threads_search_results_0">'
        + "".join(card(code, "namkiki topic") for code in codes)
        + "</div>"
    )


def thread(root, *children, ancestors=()):
    html = (
        '<div data-pagelet="threads_post_page_0">'
        + "".join(card(code, "ancestor") for code in ancestors)
        + "</div>"
    )
    html += (
        '<div data-pagelet="threads_post_page_1">'
        + card(root, "namkiki topic")
        + "</div>"
    )
    return (
        html
        + '<div data-pagelet="threads_post_page_{n}">'
        + "".join(card(code, "neutral reply 😂") for code in children)
        + "</div>"
    )


class FakeCollector:
    render = True

    def __init__(self, pages):
        self.html = pages
        self.requested = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def pages(self, page_url, scroll_limit):
        self.requested.append(page_url)
        values = self.html[page_url]
        if isinstance(values, str):
            values = [values]
        for value in values:
            if isinstance(value, BaseException):
                raise value
            yield value


@pytest.fixture
def graph():
    return {
        search_url("namkiki"): search("A"),
        search_url("pbvm"): search("B", "A"),
        url("A"): thread("A", "C", "D"),
        url("B"): thread("B", "C"),
        url("C"): thread("C", "E", ancestors=("A",)),
        url("D"): thread("D", "E"),
        url("E"): thread("E", "C"),  # cycle
    }


def options(**changes):
    return {
        "queries": ["namkiki", "pbvm"],
        "search_urls": [],
        "urls": [],
        "keywords": ["namkiki", "pbvm"],
        "negatives": [],
        "post_limit": 10,
        "comment_limit": 100,
        "scroll_limit": 3,
        "max_depth": 4,
        "max_pages": 30,
        **changes,
    }


def manifest(run_id="test"):
    return {"run_id": run_id, "sources": [], "warnings": [], "errors": []}


def test_bfs_seeds_then_posts_then_replies_and_no_cycles(tmp_path, graph):
    collector = FakeCollector(graph)
    report = manifest()
    with DatasetStore(tmp_path) as store:
        BFSCrawler(store, collector, report, options()).run()
        assert collector.requested == [
            search_url("namkiki"),
            search_url("pbvm"),
            url("A"),
            url("B"),
            url("C"),
            url("D"),
            url("E"),
        ]
        assert store.comment_ids("A") == {"C", "D", "E"}
        assert store.comment_ids("B") == {"C", "E"}
        assert store.export() == {"posts": 2, "comments": 5}
        assert report["bfs"]["stop_reason"] == "frontier_exhausted"
        assert report["bfs"]["pending"] == 0
        # C's own permalink was traversed in two root contexts, but fetched once.
        assert collector.requested.count(url("C")) == 1
        assert not report["errors"]


def test_page_budget_and_resume_without_refetching_searches(tmp_path, graph):
    first = FakeCollector(graph)
    with DatasetStore(tmp_path) as store:
        report = manifest()
        BFSCrawler(store, first, report, options(max_pages=2)).run()
        assert first.requested == [search_url("namkiki"), search_url("pbvm")]
        assert report["bfs"]["stop_reason"] == "max_pages"
        assert report["bfs"]["pending"] == 2
    # Close/reopen SQLite: queue state must survive the Python process.
    second = FakeCollector(graph)
    with DatasetStore(tmp_path) as store:
        report = manifest("resumed")
        BFSCrawler(store, second, report, options(), resume=True).run()
        assert second.requested == [url("A"), url("B"), url("C"), url("D"), url("E")]
        assert store.comment_ids("A") == {"C", "D", "E"}
        assert report["bfs"]["session_id"] == "test"


def test_depth_cap_keeps_deeper_frontier_for_resume(tmp_path, graph):
    first = FakeCollector(graph)
    with DatasetStore(tmp_path) as store:
        report = manifest()
        BFSCrawler(store, first, report, options(max_depth=1)).run()
        assert url("C") not in first.requested
        assert report["bfs"]["stop_reason"] == "max_depth"
        assert store.comment_ids("A") == {"C", "D"}
        second = FakeCollector(graph)
        BFSCrawler(store, second, manifest("next"), options(), resume=True).run()
        assert store.comment_ids("A") == {"C", "D", "E"}


def test_comment_cap_and_post_cap(tmp_path, graph):
    collector = FakeCollector(graph)
    with DatasetStore(tmp_path) as store:
        report = manifest()
        BFSCrawler(
            store, collector, report, options(post_limit=1, comment_limit=1)
        ).run()
        assert collector.requested == [
            search_url("namkiki"),
            search_url("pbvm"),
            url("A"),
        ]
        assert store.comment_ids("A") == {"C"}
        assert store.export() == {"posts": 1, "comments": 1}


def test_failed_branch_does_not_stop_other_roots_and_partial_text_survives(
    tmp_path, graph
):
    graph[url("A")] = [thread("A", "C"), RuntimeError("timeout")]
    collector = FakeCollector(graph)
    with DatasetStore(tmp_path) as store:
        report = manifest()
        BFSCrawler(store, collector, report, options()).run()
        assert store.comment_ids("A") == {"C", "E"}
        assert store.comment_ids("B") == {"C", "E"}
        assert report["errors"][0]["url"] == url("A")


def test_interrupt_resumes_inflight_page(tmp_path, graph):
    graph[url("A")] = [thread("A", "C"), KeyboardInterrupt()]
    with DatasetStore(tmp_path) as store:
        crawler = BFSCrawler(store, FakeCollector(graph), manifest(), options())
        with pytest.raises(KeyboardInterrupt):
            crawler.run()
        assert store.comment_ids("A") == {"C"}
    graph[url("A")] = thread("A", "C", "D")
    collector = FakeCollector(graph)
    with DatasetStore(tmp_path) as store:
        BFSCrawler(store, collector, manifest("resumed"), options(), resume=True).run()
        assert collector.requested[0] == url("A")
        assert store.comment_ids("A") == {"C", "D", "E"}


def test_search_seed_urls_are_normalized():
    assert canonical_search_url(
        "https://www.threads.net/search?q=namkiki&other=1"
    ) == search_url("namkiki")
    assert (
        canonical_search_url(search_url("phân biệt vùng miền"), keyword_only=True)
        == "phân biệt vùng miền"
    )
    assert canonical_search_url("https://evil.example/search?q=a") is None
    assert canonical_search_url("https://www.threads.com/search") is None


def cli_args(output, **changes):
    return argparse.Namespace(
        command="crawl",
        output=output,
        keywords=Path(__file__).resolve().parents[1] / "config/keywords.yaml",
        keyword=["namkiki", "pbvm"],
        seed_url=None,
        url=None,
        delay=3,
        render=True,
        storage_state=None,
        headed=False,
        resume=False,
        **{
            key: value
            for key, value in options().items()
            if key
            in {"post_limit", "comment_limit", "scroll_limit", "max_depth", "max_pages"}
        },
        **changes,
    )


def test_live_cli_dispatches_bfs_and_exports(tmp_path, graph, monkeypatch):
    collector = FakeCollector(graph)
    monkeypatch.setattr(main, "Collector", lambda *args: collector)
    assert main.run(cli_args(tmp_path)) == 0
    comments = [
        json.loads(line)
        for line in (tmp_path / "exports/comments.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert len(comments) == 5
    assert collector.requested[:2] == [search_url("namkiki"), search_url("pbvm")]


def test_cli_interrupt_exports_and_resume_finishes(tmp_path, graph, monkeypatch):
    graph[url("A")] = [thread("A", "C"), KeyboardInterrupt()]
    monkeypatch.setattr(main, "Collector", lambda *args: FakeCollector(graph))
    args = cli_args(tmp_path)
    assert main.run(args) == 130
    assert (tmp_path / "exports/comments.jsonl").exists()
    graph[url("A")] = thread("A", "C", "D")
    args.resume = True
    assert main.run(args) == 0
    with DatasetStore(tmp_path) as store:
        assert store.comment_ids("A") == {"C", "D", "E"}


def test_crawl_defaults_to_automatic_keyword_seeds_and_rendering(monkeypatch):
    captured = []
    monkeypatch.setattr(main, "run", lambda args: captured.append(args) or 0)
    monkeypatch.setattr("sys.argv", ["main.py", "crawl"])
    assert main.cli() == 0
    args = captured[0]
    assert args.render is True
    assert args.keyword is None and args.seed_url is None and args.url is None
    assert args.max_depth == 3 and args.max_pages == 200


def test_actual_post_snapshot_enqueues_its_eleven_comment_pages(tmp_path):
    sample = next(
        (Path(__file__).resolve().parents[1] / "sample_pages/post").glob("*.html")
    )
    root_url = "https://www.threads.com/@piarisic/post/DHH7cJyP-aZ"
    collector = FakeCollector({root_url: sample.read_text(encoding="utf-8")})
    with DatasetStore(tmp_path) as store:
        report = manifest()
        BFSCrawler(
            store, collector, report, options(queries=[], urls=[root_url], max_depth=1)
        ).run()
        assert store.comment_count("DHH7cJyP-aZ") == 11
        assert report["bfs"]["pending"] == 11
        assert report["bfs"]["stop_reason"] == "max_depth"
        assert collector.requested == [root_url]


def test_empty_search_is_successful_and_other_roots_continue(tmp_path, graph):
    graph[search_url("namkiki")] = "<html><body><span>No results.</span></body></html>"
    report = manifest()
    with DatasetStore(tmp_path) as store:
        BFSCrawler(store, FakeCollector(graph), report, options()).run()
        assert not report["errors"]
        assert store.get_post("B") is not None


def test_cleanup_interrupt_still_exports_dataset(tmp_path, graph, monkeypatch):
    class InterruptedClose(FakeCollector):
        def __exit__(self, *exc):
            raise KeyboardInterrupt

    monkeypatch.setattr(main, "Collector", lambda *args: InterruptedClose(graph))
    assert main.run(cli_args(tmp_path)) == 130
    comments = (
        (tmp_path / "exports/comments.jsonl").read_text(encoding="utf-8").splitlines()
    )
    assert len(comments) == 5


def test_cmd_single_quotes_do_not_become_part_of_output_path():
    assert main.output_path("'data/regional_discrimination'") == Path(
        "data/regional_discrimination"
    )


def test_retry_parser_errors_reuses_saved_pages(tmp_path, graph):
    graph[search_url("namkiki")] = "<html><span>No results.</span></html>"
    with DatasetStore(tmp_path) as store:
        crawler = BFSCrawler(store, FakeCollector(graph), manifest(), options())
        crawler.run()
        # Simulate the status left by the previous parser on the same actual empty page.
        with store.connection:
            store.connection.execute(
                "UPDATE bfs_frontier SET status='error',error='Search seed produced no rendered candidates.' "
                "WHERE session='test' AND url=?",
                (search_url("namkiki"),),
            )
        collector = FakeCollector(graph)
        report = manifest("retry")
        BFSCrawler(
            store, collector, report, options(), resume=True, retry_errors=True
        ).run()
        assert collector.requested == []
        assert report["errors"] == []
