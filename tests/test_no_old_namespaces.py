import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Patterns that must NOT appear anywhere in core code
# (We use more specific patterns to avoid false positives like 'score' in metrics)
BAD_PATTERNS = [
    r"band_loader",
    r"score_loader",
    r"venue_loader",
    r"BandConfig",
    r"ScoreConfig",
    r"VenueConfig",
]

IGNORE_DIRS = {
    "node_modules",
    "legacy",
    "__pycache__",
    ".git",
    "workspace",
    ".gemini"
}

def test_no_old_namespaces():
    failures = []

    for path in ROOT.rglob("*"):
        # Skip ignored directories
        if any(ignored in path.parts for ignored in IGNORE_DIRS):
            continue
            
        if not path.is_file():
            continue
            
        # Skip this test file itself
        if path.name == "test_no_old_namespaces.py":
            continue
            
        if path.suffix not in {".py", ".json", ".md"}:
            continue

        text = path.read_text(encoding="utf-8", errors="ignore")

        for pattern in BAD_PATTERNS:
            if re.search(pattern, text):
                failures.append(f"{path}: contains forbidden pattern '{pattern}'")

    assert not failures, "Old namespaces still present:\n" + "\n".join(failures)
