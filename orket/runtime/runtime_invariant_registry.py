from __future__ import annotations

import re
from pathlib import Path
from typing import Any


DEFAULT_RUNTIME_INVARIANTS_DOC_PATH = Path("docs/specs/RUNTIME_INVARIANTS.md")

_INVARIANT_PATTERN = re.compile(r"^\s*\d+\.\s+`(?P<id>INV-\d+)`:\s*(?P<statement>.+?)\s*$")


def runtime_invariant_registry_snapshot(
    *,
    doc_path: Path | str = DEFAULT_RUNTIME_INVARIANTS_DOC_PATH,
) -> dict[str, Any]:
    path = Path(doc_path)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"E_RUNTIME_INVARIANT_DOC_READ:{path}:{exc}") from exc

    invariants: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for raw_line in lines:
        match = _INVARIANT_PATTERN.match(str(raw_line or ""))
        if not match:
            continue
        invariant_id = str(match.group("id") or "").strip()
        statement = str(match.group("statement") or "").strip()
        if not invariant_id or not statement or invariant_id in seen_ids:
            continue
        seen_ids.add(invariant_id)
        invariants.append(
            {
                "invariant_id": invariant_id,
                "statement": statement,
            }
        )

    if not invariants:
        raise ValueError(f"E_RUNTIME_INVARIANT_REGISTRY_EMPTY:{path}")

    return {
        "schema_version": "1.0",
        "source_path": str(path),
        "invariants": invariants,
    }
