from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build compact summary of explorer check outputs.")
    parser.add_argument("--ingestion", required=True)
    parser.add_argument("--rollup", required=True)
    parser.add_argument("--guards", required=True)
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _status(payload: dict[str, Any]) -> str:
    return str(payload.get("status") or "UNKNOWN").strip().upper()


def main() -> int:
    args = _parse_args()
    ingestion_path = Path(args.ingestion)
    rollup_path = Path(args.rollup)
    guards_path = Path(args.guards)
    ingestion = _load(ingestion_path)
    rollup = _load(rollup_path)
    guards = _load(guards_path)

    statuses = {
        "ingestion": _status(ingestion),
        "rollup": _status(rollup),
        "guards": _status(guards),
    }
    failed = [name for name, status in statuses.items() if status not in {"PASS", "OK", "SKIP"}]
    payload = {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "status": "PASS" if not failed else "FAIL",
        "execution_lane": str(rollup.get("execution_lane") or "").strip(),
        "vram_profile": str(rollup.get("vram_profile") or "").strip(),
        "provenance_ref": str(rollup.get("provenance_ref") or "").strip(),
        "statuses": statuses,
        "failed_checks": failed,
        "artifacts": {
            "ingestion": str(ingestion_path).replace("\\", "/"),
            "rollup": str(rollup_path).replace("\\", "/"),
            "guards": str(guards_path).replace("\\", "/"),
        },
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
