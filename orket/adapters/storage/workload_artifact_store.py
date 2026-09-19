"""Verified workload projection files; application supplies publication authority."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orket.adapters.storage.verified_file import write_verified_bytes
from orket.core.contracts.protocol_hashing import sha256_hex

side_effecting = True


def prepare_artifact_root(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    raw = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    write_verified_bytes(path, raw)


def digest_file(path: Path) -> str:
    return f"sha256:{sha256_hex(path.read_bytes())}"
