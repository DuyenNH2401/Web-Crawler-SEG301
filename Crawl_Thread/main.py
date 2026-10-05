"""CLI for saved Threads pages and bounded live collection."""

import argparse
import json
import logging
import sys
import uuid
from dataclasses import asdict
from pathlib import Path

import yaml

from crawler.common.models import utc_now
from crawler.common.normalize import matched_keywords
from crawler.common.storage import DatasetStore
from crawler.threads.bfs import BFSCrawler, crawl_options
from crawler.threads.collector import CollectionError, Collector
from parsers.threads import ThreadsParser


def positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def output_path(value: str) -> Path:
    # CMD passes single quotes literally, unlike PowerShell/bash.
    if len(value) >= 2 and value[0] == value[-1] == "'":
        print(
            "Removed literal quotes from --output; use double quotes in CMD.",
            file=sys.stderr,
        )
        value = value[1:-1]
    return Path(value)


def load_keywords(path: Path) -> tuple[list[str], list[str]]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    groups = config["keywords"]
    return groups.get("primary", []) + groups.get("related", []), groups.get(
        "negative", []
    )


def write_candidates(
    store: DatasetStore, candidates: dict, keywords: list[str]
) -> None:
    folder = store.output / "exports"
    folder.mkdir(exist_ok=True)
    with (folder / "candidates.jsonl").open("w", encoding="utf-8") as output:
        for post in candidates.values():
            record = asdict(post)
            record["matched_keywords"] = matched_keywords(post.content, keywords)
            output.write(json.dumps(record, ensure_ascii=False) + "\n")


def run(args) -> int:
    if args.command == "login":
        try:
            with Collector(headed=True) as collector:
                collector.login(args.storage_state)
        except KeyboardInterrupt:
            print("Login cancelled.", file=sys.stderr)
            return 130
        return 0
    if args.command == "export":
        with DatasetStore(args.output) as store:
            print(json.dumps(store.export()))
        return 0
    parser = ThreadsParser()
    keywords, negatives = load_keywords(args.keywords)
    manifest = {
        "run_id": uuid.uuid4().hex,
        "started_at": utc_now(),
        "mode": args.command,
        "keywords": keywords,
        "negative_keywords": negatives,
        "sources": [],
        "posts_crawled": 0,
        "comments_found": 0,
        "errors": [],
        "warnings": [],
        "coverage": "loaded content only; completeness unknown",
    }
    candidates = {}
    with DatasetStore(args.output) as store:
        if args.command in {"samples", "parse", "discover"}:
            if args.command == "samples":
                post_files = sorted((args.sample_dir / "post").glob("*.html"))
                search_files = sorted((args.sample_dir / "search").glob("*.html"))
                if not post_files and not search_files:
                    raise ValueError("No HTML samples found.")
            else:
                post_files = args.html if args.command == "parse" else []
                search_files = args.html if args.command == "discover" else []
            for kind, paths in [("post", post_files), ("search", search_files)]:
                for path in paths:
                    try:
                        html = path.read_text(encoding="utf-8")
                        snapshot = store.snapshot(html, kind)
                        manifest["sources"].append(
                            {"input": str(path), "snapshot": str(snapshot)}
                        )
                        if kind == "search":
                            for post in parser.discover(html):
                                post.source_html = str(snapshot)
                                candidates.setdefault(post.post_id, post)
                        else:
                            thread = parser.parse(
                                html, getattr(args, "post_url", None), str(snapshot)
                            )
                            store.save(thread)
                            manifest["posts_crawled"] += 1
                            manifest["comments_found"] += len(thread.comments)
                            manifest["warnings"].extend(thread.warnings)
                    except (OSError, ValueError) as exc:
                        manifest["errors"].append(
                            {"source": str(path), "message": str(exc)}
                        )
        elif args.command == "crawl":
            options = crawl_options(args, keywords, negatives)
            crawler = None
            try:
                with Collector(
                    args.delay, args.render, args.storage_state, args.headed
                ) as collector:
                    crawler = BFSCrawler(
                        store,
                        collector,
                        manifest,
                        options,
                        args.resume,
                        retry_errors=getattr(args, "retry_errors", False),
                    )
                    candidates = crawler.run()
            except KeyboardInterrupt:
                manifest["warnings"].append(
                    "Interrupted; data and frontier preserved. Continue with --resume."
                )
                if crawler:
                    candidates = crawler.finish("interrupted")
        write_candidates(store, candidates, manifest["keywords"])
        manifest["search_candidates"] = len(candidates)
        manifest["warnings"] = list(dict.fromkeys(manifest["warnings"]))
        manifest["finished_at"] = utc_now()
        manifest["dataset_totals"] = store.export()
        store.save_run(manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    if manifest.get("bfs", {}).get("stop_reason") == "interrupted":
        return 130
    return 1 if manifest["errors"] else 0


def cli() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ["samples", "parse", "discover", "crawl", "export", "login"]:
        command = commands.add_parser(name)
        command.add_argument("--output", type=output_path, default=Path("data"))
        command.add_argument(
            "--keywords", type=Path, default=Path("config/keywords.yaml")
        )
        if name == "samples":
            command.add_argument(
                "--sample-dir", type=Path, default=Path("sample_pages")
            )
        if name in {"parse", "discover"}:
            command.add_argument("--html", type=Path, action="append", required=True)
        if name == "parse":
            command.add_argument("--post-url")
        if name == "login":
            command.add_argument(
                "--storage-state", type=Path, default=Path("browser_storage_state.json")
            )
        if name == "crawl":
            command.add_argument(
                "--url",
                action="append",
                help="Explicit post URL, skipping topic rejection",
            )
            command.add_argument(
                "--keyword",
                action="append",
                help="Keyword search seed; repeat for more seeds",
            )
            command.add_argument(
                "--seed-url",
                action="append",
                help="Threads search URL with a q parameter",
            )
            command.add_argument(
                "--resume",
                action="store_true",
                help="Continue the latest BFS frontier in --output",
            )
            command.add_argument(
                "--retry-errors",
                action="store_true",
                help="Retry failed jobs when resuming",
            )
            command.add_argument("--max-depth", type=positive, default=3)
            command.add_argument("--max-pages", type=positive, default=200)
            command.add_argument("--post-limit", type=positive, default=50)
            command.add_argument("--comment-limit", type=positive, default=500)
            command.add_argument("--scroll-limit", type=positive, default=20)
            command.add_argument("--delay", type=float, default=1)
            rendering = command.add_mutually_exclusive_group()
            rendering.add_argument(
                "--render",
                dest="render",
                action="store_true",
                default=True,
                help="Render with Chromium (default)",
            )
            rendering.add_argument(
                "--http-only",
                dest="render",
                action="store_false",
                help="Use plain HTTP instead of the default browser",
            )
            command.add_argument(
                "--storage-state", type=Path, help="Private Playwright session JSON"
            )
            command.add_argument("--headed", action="store_true")
    args = parser.parse_args()
    if args.command == "crawl" and args.retry_errors and not args.resume:
        parser.error("--retry-errors requires --resume")
    if args.command == "crawl" and args.render and args.storage_state is None:
        saved_session = Path("browser_storage_state.json")
        if saved_session.exists():
            args.storage_state = saved_session
    if args.command == "crawl" and args.delay < 1:
        parser.error("--delay must be at least 1 second")
    if (
        args.command == "crawl"
        and (args.storage_state or args.headed)
        and not args.render
    ):
        parser.error("--storage-state and --headed require --render")
    if args.command in {"crawl", "login"}:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        return run(args)
    except (OSError, ValueError, CollectionError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(cli())
