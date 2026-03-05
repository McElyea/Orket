from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find benchmark run records from workspace/run_manifest.jsonl.")
    parser.add_argument("--manifest", default="workspace/run_manifest.jsonl")
    parser.add_argument("--task", default="", help="Task ID filter, e.g. 011.")
    parser.add_argument("--run-id", default="", help="Run ID filter.")
    parser.add_argument("--session-id", default="", help="Session ID filter.")
    parser.add_argument("--status", default="", help="Status filter: passed|failed.")
    parser.add_argument("--latest", action="store_true", help="Return only the latest matching run.")
    parser.add_argument("--limit", type=int, default=20, help="Max records to return when not using --latest.")
    return parser.parse_args()


def _load_manifest(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _norm_task(value: str) -> str:
    stripped = str(value or "").strip()
    if stripped.isdigit():
        return stripped.zfill(3)
    return stripped


def _matches(row: dict[str, Any], args: argparse.Namespace) -> bool:
    if args.task:
        if _norm_task(str(row.get("task_id", ""))) != _norm_task(args.task):
            return False
    if args.run_id and str(row.get("run_id", "")) != str(args.run_id):
        return False
    if args.session_id and str(row.get("session_id", "")) != str(args.session_id):
        return False
    if args.status and str(row.get("status", "")).lower() != str(args.status).lower():
        return False
    return True


def main() -> int:
    args = _parse_args()
    manifest_path = Path(args.manifest)
    rows = _load_manifest(manifest_path)
    filtered = [row for row in rows if _matches(row, args)]
    filtered.sort(key=lambda row: str(row.get("started_at_utc", "")), reverse=True)

    if args.latest:
        output = filtered[:1]
    else:
        limit = max(1, int(args.limit))
        output = filtered[:limit]

    print(
        json.dumps(
            {
                "manifest": str(manifest_path).replace("\\", "/"),
                "count": len(output),
                "matches_total": len(filtered),
                "runs": output,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
