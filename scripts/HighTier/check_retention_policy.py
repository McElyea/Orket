from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List
from pathlib import Path


def _load_plan(path: str) -> Dict[str, Any]:
    payload = json.loads(open(path, "r", encoding="utf-8").read())
    if not isinstance(payload, dict):
        return {}
    return payload


def _newest_by_group(actions: List[Dict[str, Any]], namespace: str, group_key: str) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for row in actions:
        if row.get("namespace") != namespace:
            continue
        group = str(row.get(group_key) or "_unknown")
        current = grouped.get(group)
        if current is None or str(row.get("updated_at") or "") > str(current.get("updated_at") or ""):
            grouped[group] = row
    return grouped


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate retention plan safety invariants.")
    parser.add_argument("--plan", default="benchmarks/results/retention_plan.json")
    parser.add_argument("--out", default="benchmarks/results/retention_policy_check.json")
    parser.add_argument("--require-safety", action="store_true")
    args = parser.parse_args()

    plan = _load_plan(args.plan)
    actions = list(plan.get("actions") or [])
    failures: List[str] = []
    warnings: List[str] = []

    for row in actions:
        if bool(row.get("pinned")) and row.get("action") == "delete":
            failures.append(f"pinned_deleted:{row.get('path')}")
        if row.get("namespace") == "latest" and row.get("action") == "delete":
            failures.append(f"latest_deleted:{row.get('path')}")

    # Newest smoke file per profile must be retained.
    smoke_rows = [r for r in actions if r.get("namespace") == "smoke"]
    if smoke_rows:
        for row in smoke_rows:
            parts = str(row.get("path") or "").split("/")
            row["profile"] = parts[1] if len(parts) >= 2 else "_unknown"
        newest_smoke = _newest_by_group(smoke_rows, "smoke", "profile")
        for profile, row in newest_smoke.items():
            if row.get("action") != "keep":
                failures.append(f"newest_smoke_deleted:{profile}:{row.get('path')}")

    # Newest checks pass/fail per check-id must be retained when present.
    checks_rows = [r for r in actions if r.get("namespace") == "checks"]
    if checks_rows:
        for row in checks_rows:
            parts = str(row.get("path") or "").split("/")
            stem = Path(parts[2]).stem if len(parts) >= 3 else Path(str(row.get("path") or "")).stem
            if "_pass" in stem:
                stem = stem.split("_pass", 1)[0] or stem
            elif "_fail" in stem:
                stem = stem.split("_fail", 1)[0] or stem
            row["check_id"] = stem or "_unknown"
            row["status_key"] = f"{row['check_id']}:{row.get('status') or 'unknown'}"
        newest_checks = _newest_by_group(checks_rows, "checks", "status_key")
        for status_key, row in newest_checks.items():
            if str(status_key).endswith(":unknown"):
                warnings.append(f"unknown_check_status:{row.get('path')}")
                continue
            if row.get("action") != "keep":
                failures.append(f"newest_check_status_deleted:{status_key}:{row.get('path')}")

    payload = {
        "ok": len(failures) == 0,
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "failures": failures,
        "warnings": warnings,
        "checked_actions": len(actions),
    }
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(payload, ensure_ascii=False))
    if args.require_safety and failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
