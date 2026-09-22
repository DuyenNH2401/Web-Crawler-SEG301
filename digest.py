"""Build one deterministic digest from normalized articles."""

from datetime import datetime, timezone
from typing import Iterable

from models import Article, Digest


def build_digest(articles: Iterable[Article], topic: str = "News & Information") -> Digest:
    items = list(articles)
    sections = [f"# {topic}", "", f"Nguồn đã crawl: {len(items)}", ""]

    for article in items:
        sections.extend(
            [
                f"## {article.source}: {article.title}",
                f"Nguồn: {article.url}",
                "",
                article.content.strip(),
                "",
            ]
        )

    if not items:
        sections.append("Chưa crawl được bài báo nào.")

    return Digest(
        topic=topic,
        articles=items,
        content="\n".join(sections).strip() + "\n",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
