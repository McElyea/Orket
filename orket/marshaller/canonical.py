from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> str:
    """Return deterministic JSON with stable key ordering and compact separators."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sha256_hex(value: str | bytes) -> str:
    payload = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(payload).hexdigest()


def hash_canonical_json(value: Any) -> str:
    return sha256_hex(canonical_json(value))


def compute_tree_digest(root: Path) -> str:
    """
    Compute a deterministic digest for a working tree.

    Digest input is canonical JSON over sorted relative file entries.
    """

    entries: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel == ".git" or rel.startswith(".git/"):
            continue
        payload = path.read_bytes()
        entries.append(
            {
                "path": rel,
                "digest": sha256_hex(payload),
            }
        )
    return hash_canonical_json(entries)

