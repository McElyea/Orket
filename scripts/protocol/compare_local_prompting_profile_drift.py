from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare local prompting profile snapshots.")
    parser.add_argument("--before", required=True, help="Path to baseline profile snapshot JSON.")
    parser.add_argument("--after", required=True, help="Path to candidate profile snapshot JSON.")
    parser.add_argument(
        "--out",
        default="benchmarks/results/protocol/local_prompting/drift/latest/profile_delta_report.json",
        help="Canonical drift report output path.",
    )
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when differences are detected.")
    return parser


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _profile_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("profiles")
    if not isinstance(rows, list):
        return {}
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        profile = row.get("profile")
        if not isinstance(profile, dict):
            continue
        profile_id = str(profile.get("profile_id") or "").strip()
        if not profile_id:
            continue
        indexed[profile_id] = row
    return indexed


def _compare(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_index = _profile_index(before)
    after_index = _profile_index(after)
    before_ids = set(before_index.keys())
    after_ids = set(after_index.keys())
    added = sorted(after_ids - before_ids)
    removed = sorted(before_ids - after_ids)
    modified: list[dict[str, Any]] = []
    for profile_id in sorted(before_ids & after_ids):
        if before_index[profile_id] == after_index[profile_id]:
            continue
        modified.append(
            {
                "profile_id": profile_id,
                "before_hash": hashlib.sha256(
                    json.dumps(before_index[profile_id], sort_keys=True).encode("utf-8")
                ).hexdigest(),
                "after_hash": hashlib.sha256(
                    json.dumps(after_index[profile_id], sort_keys=True).encode("utf-8")
                ).hexdigest(),
            }
        )
    changed = bool(added or removed or modified)
    return {
        "schema_version": "local_prompting_profile_drift.v1",
        "changed": changed,
        "added_profiles": added,
        "removed_profiles": removed,
        "modified_profiles": modified,
        "before_count": len(before_index),
        "after_count": len(after_index),
    }


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    before = _load_json(Path(str(args.before)).resolve())
    after = _load_json(Path(str(args.after)).resolve())
    payload = _compare(before, after)
    out_path = Path(str(args.out)).resolve()
    write_payload_with_diff_ledger(out_path, payload)
    if bool(args.strict) and bool(payload.get("changed")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
