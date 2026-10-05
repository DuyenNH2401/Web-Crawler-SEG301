import re
import unicodedata
from datetime import datetime, timedelta

import config

_UNIT_SECONDS = {
    "second": 1, "minute": 60, "hour": 3600, "day": 86400,
    "week": 7 * 86400, "month": 30 * 86400, "year": 365 * 86400,
    "giây": 1, "phút": 60, "giờ": 3600, "ngày": 86400,
    "tuần": 7 * 86400, "tháng": 30 * 86400, "năm": 365 * 86400,
}
_RELATIVE_RE = re.compile(
    r"(\d+)\s*(second|minute|hour|day|week|month|year|giây|phút|giờ|ngày|tuần|tháng|năm)",
    re.IGNORECASE,
)


def parse_relative_time(text, reference):
    if not text:
        return None
    lowered = text.lower()
    if "just now" in lowered or "vừa xong" in lowered:
        return reference
    m = _RELATIVE_RE.search(lowered)
    if not m:
        return None
    amount = int(m.group(1))
    unit = m.group(2).lower()
    return reference - timedelta(seconds=amount * _UNIT_SECONDS[unit])


_MULTIPLIER = {"": 1, "k": 1_000, "m": 1_000_000, "b": 1_000_000_000}
_LIKE_RE = re.compile(r"(\d+(?:[.,]\d+)*)\s*([kmb]?)", re.IGNORECASE)


def parse_like_count(text):
    if not text:
        return 0
    m = _LIKE_RE.search(str(text).strip())
    if not m:
        return 0
    number, suffix = m.group(1), m.group(2).lower()
    if suffix:
        value = float(number.replace(",", "."))
    else:
        value = float(re.sub(r"[.,]", "", number))
    return int(round(value * _MULTIPLIER[suffix]))


_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)


def count_words(text):
    return len(_WORD_RE.findall(text or ""))


def _fold(text):
    return unicodedata.normalize("NFC", text or "").casefold()


def compile_keywords(keywords):
    compiled = []
    for keyword in keywords or []:
        words = _fold(keyword).split()
        if not words:
            continue
        body = r"\s+".join(re.escape(word) for word in words)
        compiled.append((keyword.strip(), re.compile(rf"(?<![^\W_]){body}(?![^\W_])")))
    return compiled


def match_keywords(text, compiled):
    value = _fold(text)
    return [keyword for keyword, pattern in compiled if pattern.search(value)]


def build_comment_url(video_id, comment_id):
    return f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}"


def to_record(raw, video_id, parent_id, collected_at):
    comment_id = (raw.get("comment_id") or "").strip()
    content = (raw.get("content") or "").strip()
    if not comment_id or not content:
        return None

    created = parse_relative_time(raw.get("published_text"), collected_at)
    return {
        "platform": config.PLATFORM,
        "comment_id": comment_id,
        "content": content,
        "author_id": (raw.get("author_id") or "").strip() or config.UNKNOWN,
        "author_name": (raw.get("author_name") or "").strip() or config.UNKNOWN,
        "parent_id": parent_id or config.ROOT,
        "post_id": video_id,
        "comment_url": build_comment_url(video_id, comment_id),
        "created_at": (created or collected_at).strftime(config.TIME_FORMAT),
        "like_count": parse_like_count(raw.get("like_text")),
        "collected_at": collected_at.strftime(config.TIME_FORMAT),
    }


def now():
    return datetime.now(config.TIMEZONE).replace(microsecond=0)
