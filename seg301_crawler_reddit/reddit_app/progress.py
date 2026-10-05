"""Hiển thị tiến trình bằng một thread chỉ đọc trạng thái và ghi log."""
from __future__ import annotations

import math
import threading
import time
from typing import Any, Callable

from .config import DEFAULT_PROGRESS_INTERVAL, LOG


class CrawlProgress:
    """Log crawl counters periodically even while the main thread waits on I/O."""

    def __init__(self, total: int, *, dry_run: bool = False, interval: float = DEFAULT_PROGRESS_INTERVAL,
                 emit: Callable[[str], None] | None = None):
        if total <= 0 or not math.isfinite(interval) or interval <= 0:
            raise ValueError("invalid progress limits")
        self.total = total
        self.dry_run = dry_run
        self.interval = interval
        self.emit = emit or LOG.info
        self.saved = 0
        self.posts = 0
        self.stage = "Chuẩn bị database"
        self.started = time.monotonic()
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.worker = threading.Thread(target=self._run, name="reddit-progress", daemon=True)

    def __enter__(self) -> CrawlProgress:
        self.started = time.monotonic()
        self.report()
        self.worker.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.stop.set()
        self.worker.join()
        stage = "Hoàn tất" if exc_type is None else "Đã dừng" if isinstance(exc, KeyboardInterrupt) else "Lỗi"
        self.update(stage=stage, report=True)

    def _run(self) -> None:
        while not self.stop.wait(self.interval):
            self.report()

    def update(self, *, saved: int | None = None, posts: int | None = None,
               stage: str | None = None, report: bool = False) -> None:
        with self.lock:
            if saved is not None:
                self.saved = saved
            if posts is not None:
                self.posts = posts
            if stage is not None:
                self.stage = stage
            if report:
                self.report()

    def report(self) -> None:
        with self.lock:
            elapsed = max(0, int(time.monotonic() - self.started))
            hours, remainder = divmod(elapsed, 3600)
            minutes, seconds = divmod(remainder, 60)
            filled = min(20, max(0, self.saved * 20 // self.total))
            bar = "#" * filled + "-" * (20 - filled)
            label = self.stage if self.stage in {"Hoàn tất", "Đã dừng", "Lỗi"} else "Đang cào"
            if self.dry_run:
                label += " (dry-run)"
            self.emit(f"[{bar}] {label} {self.saved}/{self.total} comment | bài={self.posts} | "
                      f"elapsed={hours:02d}:{minutes:02d}:{seconds:02d} | {self.stage}")
