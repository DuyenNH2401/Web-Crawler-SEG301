"""Dữ liệu của một chủ đề VOZ."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Thread:
    thread_id: str
    title: str
    url: str
