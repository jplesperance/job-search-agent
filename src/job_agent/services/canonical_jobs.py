from __future__ import annotations

import re
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_KEYS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gh_src", "ref", "referrer",
}
_LEGAL_SUFFIXES = {"inc", "incorporated", "llc", "corp", "corporation", "ltd", "limited", "co"}


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = value.casefold().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def normalize_company(value: str | None) -> str:
    words = normalize_text(value).split()
    while words and words[-1] in _LEGAL_SUFFIXES:
        words.pop()
    return " ".join(words)


def normalize_title(value: str | None) -> str:
    aliases = {"sr": "senior", "jr": "junior"}
    return " ".join(aliases.get(word, word) for word in normalize_text(value).split())


def normalize_location(value: str | None) -> str:
    return normalize_text(value)


def normalize_source_url(value: str | None) -> str | None:
    if not value:
        return None
    parts = urlsplit(value.strip())
    query = [
        (key, val)
        for key, val in parse_qsl(parts.query, keep_blank_values=True)
        if key.casefold() not in _TRACKING_KEYS
    ]
    path = re.sub(r"/+", "/", parts.path or "/").rstrip("/") or "/"
    return urlunsplit(
        (
            parts.scheme.casefold() or "https",
            parts.netloc.casefold(),
            path,
            urlencode(query, doseq=True),
            "",
        )
    )


def description_similarity(left: str | None, right: str | None) -> float:
    left_n = normalize_text(left)
    right_n = normalize_text(right)
    if not left_n or not right_n:
        return 0.0
    if left_n == right_n:
        return 1.0
    return SequenceMatcher(None, left_n, right_n, autojunk=True).ratio()
