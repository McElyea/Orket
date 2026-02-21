from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build compact rollup from context ceiling artifact.")
    parser.add_argument("--context-ceiling", required=True)
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Expected JSON object")
    return payload


def main() -> int:
    args = _parse_args()
    ceiling = _load(Path(args.context_ceiling))
    points = ceiling.get("points") if isinstance(ceiling.get("points"), list) else []
    passed = [point for point in points if isinstance(point, dict) and bool(point.get("passed"))]
    failed = [point for point in points if isinstance(point, dict) and not bool(point.get("passed"))]
    out_payload = {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "schema_version": "explorer.context_sweep_rollup.v1",
        "source_context_ceiling": str(Path(args.context_ceiling)).replace("\\", "/"),
        "execution_lane": str(ceiling.get("execution_lane") or ""),
        "vram_profile": str(ceiling.get("vram_profile") or ""),
        "provenance": ceiling.get("provenance") if isinstance(ceiling.get("provenance"), dict) else {},
        "safe_context_ceiling": ceiling.get("safe_context_ceiling"),
        "contexts_total": len(points),
        "contexts_passed": len(passed),
        "contexts_failed": len(failed),
        "failed_contexts": [point.get("context") for point in failed if isinstance(point.get("context"), int)],
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out_payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out_payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
