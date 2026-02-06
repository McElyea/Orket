import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Patterns that must NOT appear anywhere
BAD_PATTERNS = [
    r"\bbands?\b",
    r"\bscores?\b",
    r"\bvenues?\b",
    r"band_loader",
    r"score_loader",
    r"venue_loader",
]

def test_no_old_namespaces():
    failures = []

    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in {".py", ".json", ".md"}:
            continue

        text = path.read_text(encoding="utf-8", errors="ignore")

        for pattern in BAD_PATTERNS:
            if re.search(pattern, text):
                failures.append(f"{path}: contains forbidden pattern '{pattern}'")

    assert not failures, "Old namespaces still present:\n" + "\n".join(failures)