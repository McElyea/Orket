from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orket.runtime.migrations.workitem_mapper import map_legacy_records


def _load_input(path: Path) -> List[Dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Input must be a JSON list of legacy records.")
    output: List[Dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            output.append(item)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic dry-run mapping report for WorkItem migration.")
    parser.add_argument("--in", dest="input_path", required=True, help="Path to legacy records JSON list.")
    parser.add_argument("--out", default="benchmarks/results/workitem_migration_dry_run.json")
    args = parser.parse_args()

    input_path = Path(args.input_path)
    out_path = Path(args.out)
    records = _load_input(input_path)
    mapped = map_legacy_records(records)
    kind_counts = Counter(str(item.get("kind") or "") for item in mapped)
    report = {
        "status": "PASS",
        "mode": "dry_run",
        "input_path": str(input_path),
        "total_records": len(records),
        "mapped_kind_counts": dict(sorted(kind_counts.items())),
        "records": mapped,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"status": report["status"], "total_records": report["total_records"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
