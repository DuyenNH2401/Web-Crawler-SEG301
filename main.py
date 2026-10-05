"""Choose a social crawler and use one SQLite comments database."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

from shared_database import DEFAULT_DB, import_existing

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in {"x", "reddit", "youtube", "tiktok", "thread", "threads", "migrate", "--db", "-h", "--help"}:
        # Preserve the previous X-only command line for existing scripts.
        from x_crawler.main import main as x_main
        return x_main(argv)
    if argv and argv[0] == "reddit" and any(arg in {"-h", "--help"} for arg in argv[1:]):
        from reddit_cli import main as reddit_main
        return reddit_main(argv[1:], str(DEFAULT_DB))
    if len(argv) >= 2 and argv[0] == "x" and argv[1] in {"-h", "--help"}:
        from x_crawler.main import main as x_main
        return x_main(argv[1:])
    if len(argv) >= 2 and argv[0] == "youtube" and argv[1] in {"-h", "--help"}:
        script = Path(__file__).resolve().parent / "youtube-comment-crawler" / "main.py"
        return subprocess.call([sys.executable, str(script), argv[1]])
    if len(argv) >= 2 and argv[0] == "tiktok" and argv[1] in {"-h", "--help"}:
        from tiktok_crawler.main import main as tiktok_main
        return tiktok_main(argv[1:]) or 0
    if len(argv) >= 2 and argv[0] in {"thread", "threads"} and argv[1] in {"-h", "--help"}:
        from threads_cli import run as threads_run
        return threads_run(argv[1:], str(DEFAULT_DB))
    cli = argparse.ArgumentParser(
        description="Cào bình luận X, Reddit, YouTube, TikTok hoặc Threads vào cùng một database",
        usage="python main.py [--db PATH] {x,reddit,youtube,tiktok,threads,migrate} [tham số crawler]")
    cli.add_argument("--db", default=str(DEFAULT_DB), help="File SQLite chung (mặc định: data/comments.db)")
    cli.add_argument("platform", choices=("x", "reddit", "youtube", "tiktok", "thread", "threads", "migrate"))
    args, rest = cli.parse_known_args(argv)
    db_path = str(Path(args.db).resolve())

    if args.platform == "migrate":
        if rest:
            cli.error("migrate không nhận tham số khác")
        counts = import_existing(db_path)
        print("Đã nhập vào {}: {}".format(db_path, ", ".join(
            f"{name} {count}" for name, count in counts.items())))
        return 0
    if args.platform == "x":
        from x_crawler.main import main as x_main
        return x_main([*rest, "--db", db_path])
    if args.platform == "reddit":
        from reddit_cli import main as reddit_main
        return reddit_main(rest, db_path)
    if args.platform == "youtube":
        script = Path(__file__).resolve().parent / "youtube-comment-crawler" / "main.py"
        if not script.is_file():
            cli.error(f"Không tìm thấy crawler YouTube: {script}")
        command = [sys.executable, str(script), *rest, "--db", db_path]
        return subprocess.call(command)
    if args.platform == "tiktok":
        from tiktok_crawler.main import main as tiktok_main
        return tiktok_main([*rest, "--db", db_path]) or 0
    if args.platform in {"thread", "threads"}:
        from threads_cli import run as threads_run
        return threads_run(rest, db_path)
    cli.error("Nền tảng không được hỗ trợ")


if __name__ == "__main__":
    raise SystemExit(main())
