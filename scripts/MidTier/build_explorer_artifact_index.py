from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build explorer artifact index for downstream ingestion.")
    parser.add_argument("--frontier", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--thermal", required=True)
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _row(kind: str, path: Path) -> dict[str, Any]:
    payload = _load(path)
    provenance = payload.get("provenance") if isinstance(payload.get("provenance"), dict) else {}
    return {
        "kind": kind,
        "path": str(path).replace("\\", "/"),
        "schema_version": str(payload.get("schema_version") or ""),
        "generated_at": str(payload.get("generated_at") or ""),
        "execution_lane": str(payload.get("execution_lane") or ""),
        "vram_profile": str(payload.get("vram_profile") or ""),
        "provenance_ref": str(provenance.get("ref") or ""),
    }


def main() -> int:
    args = _parse_args()
    rows = [
        _row("frontier", Path(args.frontier)),
        _row("context", Path(args.context)),
        _row("thermal", Path(args.thermal)),
    ]
    out_payload = {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "rows": rows,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out_payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out_payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
