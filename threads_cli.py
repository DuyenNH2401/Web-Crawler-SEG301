"""Run the Threads subproject and copy its comments to shared SQLite."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from shared_database import ROOT, import_threads_dataset


THREADS_DIR = ROOT / "Crawl_Thread"
PATH_OPTIONS = {"--output", "--html", "--sample-dir", "--keywords", "--storage-state"}


def run(argv: list[str], db_path: str) -> int:
    script = THREADS_DIR / "main.py"
    if not script.is_file():
        raise FileNotFoundError(f"Không tìm thấy crawler Threads: {script}")
    forwarded = []
    output = THREADS_DIR / "data"
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg in PATH_OPTIONS and index + 1 < len(argv):
            path = Path(argv[index + 1]).resolve()
            forwarded.extend((arg, str(path)))
            if arg == "--output":
                output = path
            index += 2
            continue
        key, sep, value = arg.partition("=")
        if sep and key in PATH_OPTIONS:
            path = Path(value).resolve()
            forwarded.append(f"{key}={path}")
            if key == "--output":
                output = path
        else:
            forwarded.append(arg)
        index += 1
    result = subprocess.call([sys.executable, str(script), *forwarded], cwd=THREADS_DIR)
    if argv and argv[0] not in {"login", "-h", "--help"}:
        source = output / "dataset.sqlite3"
        if source.is_file():
            count = import_threads_dataset(db_path, source)
            print(f"Đã đồng bộ {count} bình luận Threads mới vào {db_path}")
    return result
