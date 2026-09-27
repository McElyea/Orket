"""Pure record-diff and physical-rehash helpers for catalog restart proofs."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _flatten_record(value: Any, path: str = "$") -> dict[str, dict[str, Any]]:
    row: dict[str, Any] = {"type": type(value).__name__}
    rows = {path: row}
    if isinstance(value, dict):
        row["keys"] = sorted(value)
        for key in sorted(value):
            rows.update(_flatten_record(value[key], f"{path}.{key}"))
    elif isinstance(value, list):
        row["length"] = len(value)
        for index, item in enumerate(value):
            rows.update(_flatten_record(item, f"{path}[{index}]"))
    else:
        row["value"] = value
    return rows


def difference_rows(left: Any, right: Any) -> list[dict[str, Any]]:
    left_rows, right_rows = _flatten_record(left), _flatten_record(right)
    return [
        {"path": path, "left": left_rows.get(path), "right": right_rows.get(path)}
        for path in sorted(set(left_rows) | set(right_rows))
        if left_rows.get(path) != right_rows.get(path)
    ]


def rehash_paths(install: dict[str, Any], restart: dict[str, Any]) -> dict[str, str]:
    expected = {
        install["physical"]["catalog"]["path"]: install["physical"]["catalog"]["sha256"],
    }
    for pair in install["physical"]["files"].values():
        expected[pair["source"]["path"]] = pair["source"]["sha256"]
        expected[pair["checkout"]["path"]] = pair["checkout"]["sha256"]
    for name in ("artifact", "artifact_manifest", "provenance"):
        row = restart["physical"][name]
        assert row["path"] not in expected
        expected[row["path"]] = row["sha256"]
    assert len(expected) == 10
    observed = {path: _sha256(Path(path)) for path in sorted(expected)}
    assert observed == dict(sorted(expected.items()))
    return observed
