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


def test_no_legacy_shim_imports_in_code():
    repo_root = Path(__file__).resolve().parents[2]
    legacy_import_tokens = [
        "from orket.llm import",
        "from orket.services.prompt_compiler import",
        "from orket.services.tool_parser import",
        "from orket.services.webhook_db import",
        "from orket.services.gitea_webhook_handler import",
        "from orket.infrastructure.async_card_repository import",
        "from orket.infrastructure.async_file_tools import",
        "from orket.infrastructure.async_repositories import",
        "from orket.infrastructure.sqlite_repositories import",
        "from orket.infrastructure.command_runner import",
        "from orket.tool_runtime import",
        "from orket.tool_strategy.default import",
        "from orket.tool_families",
        "from orket.orchestration.orchestrator import",
        "from orket.orchestration.turn_executor import",
    ]
    failures = []
    for path in repo_root.rglob("*.py"):
        if any(ignored in path.parts for ignored in IGNORE_DIRS):
            continue
        if path.name == "test_no_old_namespaces.py":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in legacy_import_tokens:
            if token in text:
                failures.append(f"{path}: contains legacy import token '{token}'")
    assert not failures, "Legacy shim imports still present:\n" + "\n".join(failures)

