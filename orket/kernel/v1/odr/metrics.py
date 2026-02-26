from __future__ import annotations

import re
from typing import List, Set

from .parsers import normalize_newlines


def normalize_text(text: str) -> str:
    normalized = normalize_newlines(text).lower()
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def tokenize(text: str) -> List[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    return normalized.split(" ")


def shingles(tokens: List[str], k: int) -> Set[str]:
    if len(tokens) < int(k):
        return set()
    return {" ".join(tokens[i : i + k]) for i in range(0, len(tokens) - k + 1)}


def jaccard_sim(a: str, b: str, k: int) -> float:
    sa = shingles(tokenize(a), int(k))
    sb = shingles(tokenize(b), int(k))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def diff_ratio(curr: str, prev: str) -> float:
    return abs(len(str(curr)) - len(str(prev))) / max(1, len(str(prev)))
