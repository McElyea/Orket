from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_KINDS = {"frontier", "context", "thermal"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate explorer artifact index for ingestion readiness.")
    parser.add_argument("--index", required=True, help="Path to explorer_artifact_index.json")
    parser.add_argument("--out", default="", help="Optional output report path")
    return parser.parse_args()


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Index payload must be a JSON object")
    return payload


def main() -> int:
    args = _parse_args()
    payload = _load(Path(args.index))
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    failures: list[str] = []
    found_kinds: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            failures.append("INVALID_ROW_TYPE")
            continue
        kind = str(row.get("kind") or "").strip()
        if kind:
            found_kinds.add(kind)
        if not str(row.get("schema_version") or "").strip():
            failures.append(f"{kind}:MISSING_SCHEMA_VERSION")
        if not str(row.get("provenance_ref") or "").strip():
            failures.append(f"{kind}:MISSING_PROVENANCE_REF")
    missing_kinds = sorted(REQUIRED_KINDS - found_kinds)
    if missing_kinds:
        failures.append(f"MISSING_REQUIRED_KINDS:{','.join(missing_kinds)}")

    report = {
        "status": "PASS" if not failures else "FAIL",
        "index": str(Path(args.index)).replace("\\", "/"),
        "required_kinds": sorted(REQUIRED_KINDS),
        "found_kinds": sorted(found_kinds),
        "failures": failures,
    }
    text = json.dumps(report, indent=2)
    print(text)
    if str(args.out or "").strip():
        out_path = Path(str(args.out))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
