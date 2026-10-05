"""Regression tests against the user's real downloaded Threads pages."""

import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from crawler.common.normalize import matched_keywords, normalize_text
from crawler.common.storage import DatasetStore
from parsers.threads import ParseError, ThreadsParser, canonical_post_url, parse_count

ROOT = Path(__file__).resolve().parents[1]
POST_URL = "https://www.threads.com/@piarisic/post/DHH7cJyP-aZ"
EXPECTED = (
    "Nhiều thằng hà nội tự gọi cái tàu trên cao đó là metro, dân ngoài đó tư duy cl gì vậy? "
    "Metro là phải có hầm ngầm nhé, tư duy như vậy nên không có gs25 là đúng rồi"
)


@pytest.fixture(scope="module")
def post_html():
    return next((ROOT / "sample_pages/post").glob("*.html")).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def search_html():
    return next((ROOT / "sample_pages/search").glob("*.html")).read_text(
        encoding="utf-8"
    )


def test_exact_requested_vietnamese_comment(post_html):
    result = ThreadsParser().parse(post_html)
    assert result.post.post_id == "DHH7cJyP-aZ"
    assert result.post.content == "Trong nam có từ đời tống mà h bắc mới có :))"
    assert result.post.created_at == "2025-03-13T03:08:32+00:00"
    assert result.post.like_count == 194
    assert len(result.comments) == 11
    comment = next(c for c in result.comments if c.comment_id == "DHKOKsfSu0F")
    assert comment.content == EXPECTED
    assert comment.author_name == "_progamer_2133"
    assert (
        comment.comment_url
        == "https://www.threads.com/@_progamer_2133/post/DHKOKsfSu0F"
    )
    assert comment.created_at == "2025-03-14T00:30:39+00:00"
    assert comment.like_count == 3
    assert all("Translate" not in c.content for c in result.comments)
    assert all(c.parent_id == "UNKNOWN" for c in result.comments)
    reply = next(c for c in result.comments if c.comment_id == "DHKYVO7ycK1")
    assert reply.reply_group_id == comment.comment_id
    assert reply.parent_id == "UNKNOWN"


def test_search_excludes_adjacent_feed_and_deduplicates(search_html):
    results = ThreadsParser().discover(search_html)
    assert len(results) == 15
    assert len({p.post_id for p in results}) == 15
    assert "DeELtWfks_X" not in {p.post_id for p in results}  # For you hair salon ad
    assert "DaHYd4TEYH3" in {p.post_id for p in results}
    paragraphs = next(p for p in results if p.post_id == "DVc4f0HEvKW")
    assert "Tại vì người bắc" in paragraphs.content
    assert "Còn người nam" in paragraphs.content
    assert "Replying to" not in paragraphs.content
    assert "Translate" not in paragraphs.content


def test_opaque_classes_are_not_required(post_html):
    soup = BeautifulSoup(post_html, "lxml")
    for tag in soup.select("[class]"):
        del tag["class"]
    result = ThreadsParser().parse(str(soup))
    assert len(result.comments) == 11
    assert (
        next(c.content for c in result.comments if c.comment_id == "DHKOKsfSu0F")
        == EXPECTED
    )


def test_broken_snapshot_does_not_silently_succeed(post_html, search_html):
    with pytest.raises(ParseError):
        ThreadsParser().parse("<html>Log in</html>", POST_URL)
    with pytest.raises(ParseError):
        ThreadsParser().discover(post_html)
    with pytest.raises(ParseError):
        ThreadsParser().parse(search_html)
    with pytest.raises(ParseError):
        ThreadsParser().parse(post_html, "https://www.threads.com/@a/post/missing")


def test_absent_fields_are_not_fabricated(post_html):
    soup = BeautifulSoup(post_html, "lxml")
    for node in soup.select("time"):
        node.attrs.pop("datetime", None)
    result = ThreadsParser().parse(str(soup))
    assert result.post.created_at is None
    assert result.post.author_id == "UNKNOWN"
    assert result.post.text_may_be_truncated is None
    assert all(c.created_at is None for c in result.comments)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("4.4K", (4400, True)),
        ("1,234", (1234, False)),
        ("", (None, False)),
        ("0", (0, False)),
    ],
)
def test_displayed_counts(value, expected):
    assert parse_count(value) == expected


def test_urls_and_keyword_normalization():
    assert (
        canonical_post_url("https://www.threads.net/@a/post/abc/media?x=1")
        == "https://www.threads.com/@a/post/abc"
    )
    assert canonical_post_url("https://evil.example/@a/post/abc") is None
    assert canonical_post_url("javascript:alert(1)") is None
    assert normalize_text("Nhiều\n   thằng\u00a0hà nội😂") == "Nhiều thằng hà nội😂"
    assert matched_keywords("NAMKIKI", ["namkiki"]) == ["namkiki"]
    assert not matched_keywords("namkikix", ["namkiki"])
    assert matched_keywords("BẮC KỲ", ["bắc kỳ"]) == ["bắc kỳ"]


def test_reruns_are_deduplicated_and_utf8_export_roundtrips(post_html, tmp_path):
    result = ThreadsParser().parse(post_html)
    with DatasetStore(tmp_path) as store:
        store.save(result)
        store.save(result)
        assert store.export() == {"posts": 1, "comments": 11}
        snapshot = store.snapshot(post_html, "post")
        assert snapshot.read_text(encoding="utf-8") == post_html
    records = [
        json.loads(line)
        for line in (tmp_path / "exports/comments.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert (
        next(c["content"] for c in records if c["comment_id"] == "DHKOKsfSu0F")
        == EXPECTED
    )
    assert (tmp_path / "exports/comments.csv").read_bytes().startswith(b"\xef\xbb\xbf")


def test_invalid_record_rolls_back(post_html, tmp_path):
    result = ThreadsParser().parse(post_html)
    result.comments[0].content = ""
    with DatasetStore(tmp_path) as store:
        with pytest.raises(ValueError):
            store.save(result)
        assert store.export() == {"posts": 0, "comments": 0}


def test_actual_guest_no_results_is_not_a_parser_failure():
    html = (ROOT / "fixtures/threads/guest_no_results.html").read_text(encoding="utf-8")
    parser = ThreadsParser()
    assert parser.discover(html) == []
    assert parser.parse_search(html).state == "empty"


def test_actual_guest_results_are_flagged_as_login_limited():
    html = (ROOT / "fixtures/threads/guest_search_results.html").read_text(
        encoding="utf-8"
    )
    result = ThreadsParser().parse_search(html)
    assert result.posts
    assert result.login_limited


def test_login_wall_is_distinct_from_empty_search():
    with pytest.raises(ParseError, match="AUTH_REQUIRED"):
        ThreadsParser().discover("<html><body>Log in to continue</body></html>")
