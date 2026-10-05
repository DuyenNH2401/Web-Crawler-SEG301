"""Keep original spelling, accents, emoji and punctuation in dataset text."""

import re
import unicodedata


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


def matched_keywords(text: str, keywords: list[str]) -> list[str]:
    text = normalize_text(text).casefold()
    return [
        k
        for k in keywords
        if re.search(
            r"(?<!\w)" + re.escape(normalize_text(k).casefold()) + r"(?!\w)", text
        )
    ]
