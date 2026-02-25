from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orket.runtime.retention_policy import RetentionPolicy, build_retention_plan


def _parse_dt(value: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        return datetime.now(UTC)
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _collect_local_entries(root: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not root.exists():
        return rows
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        stat = path.stat()
        rows.append(
            {
                "path": str(path.relative_to(root)).replace("\\", "/"),
                "size_bytes": int(stat.st_size),
                "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
                "pinned": False,
            }
        )
    return rows


def _load_inventory(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("entries"), list):
        return [row for row in payload["entries"] if isinstance(row, dict)]
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate retention dry-run plan for artifacts/checks/smoke namespaces.")
    parser.add_argument("--root", default="benchmarks/results", help="Local results root to scan when --inventory is omitted.")
    parser.add_argument("--inventory", default="", help="Optional JSON inventory file ({entries:[...]} or list).")
    parser.add_argument("--as-of", default="", help="Anchor timestamp in ISO format (default now UTC).")
    parser.add_argument("--smoke-days", type=int, default=14)
    parser.add_argument("--smoke-keep-latest", type=int, default=50)
    parser.add_argument("--checks-days", type=int, default=60)
    parser.add_argument("--artifacts-days", type=int, default=30)
    parser.add_argument("--artifacts-size-cap-gb", type=int, default=200)
    parser.add_argument("--out", default="benchmarks/results/retention_plan.json")
    args = parser.parse_args()

    if args.inventory:
        entries = _load_inventory(Path(args.inventory))
    else:
        entries = _collect_local_entries(Path(args.root))

    policy = RetentionPolicy(
        smoke_days=max(1, int(args.smoke_days)),
        smoke_keep_latest_per_profile=max(1, int(args.smoke_keep_latest)),
        checks_days=max(1, int(args.checks_days)),
        artifacts_days=max(1, int(args.artifacts_days)),
        artifacts_size_cap_bytes=max(1, int(args.artifacts_size_cap_gb)) * 1024 * 1024 * 1024,
    )
    plan = build_retention_plan(entries, as_of=_parse_dt(args.as_of), policy=policy)
    plan["source"] = {
        "root": str(args.root),
        "inventory": str(args.inventory or ""),
        "entry_count": len(entries),
        "mode": "dry-run",
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out_path), "summary": plan.get("summary", {})}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
