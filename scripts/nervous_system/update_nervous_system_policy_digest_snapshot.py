"""Refresh the nervous-system policy digest snapshot fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orket.kernel.v1.nervous_system_policy_snapshot import (
    build_policy_digest_contributors,
    build_policy_digest_snapshot,
)

DEFAULT_SNAPSHOT_PATH = Path("tests/fixtures/nervous_system_policy_digest_snapshot.json")


def _serialize(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _load_existing(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _diff_dict(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    prefix: str = "",
) -> list[str]:
    changes: list[str] = []
    keys = sorted(set(before.keys()) | set(after.keys()))
    for key in keys:
        dotted = f"{prefix}{key}"
        if key not in before:
            changes.append(f"+ {dotted}: added")
            continue
        if key not in after:
            changes.append(f"- {dotted}: removed")
            continue
        left = before[key]
        right = after[key]
        if left == right:
            continue
        if isinstance(left, dict) and isinstance(right, dict):
            changes.extend(_diff_dict(left, right, prefix=f"{dotted}."))
            continue
        changes.append(f"~ {dotted}: {left!r} -> {right!r}")
    return changes


def _print_changes(changes: list[str]) -> None:
    if not changes:
        print("[OK] No snapshot changes detected.")
        return
    print("[OK] Snapshot changes:")
    for line in changes:
        print(f"  {line}")


def _write_snapshot(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_serialize(payload), encoding="utf-8")


def _print_explain() -> None:
    contributors = build_policy_digest_contributors()
    print("[EXPLAIN] Digest contributors:")
    for group_name in ("policy_contexts", "deny_rules", "tool_profiles"):
        entries = list(contributors.get(group_name) or [])
        print(f"  {group_name}:")
        for entry in entries:
            name = str(entry.get("name") or "")
            digest = str(entry.get("digest") or "")
            source_path = str(entry.get("source_path") or "")
            rule_name = str(entry.get("rule_name") or "")
            print(f"    - {name}")
            print(f"      digest: {digest}")
            print(f"      source_path: {source_path}")
            print(f"      rule_name: {rule_name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Update nervous-system policy digest snapshot.")
    parser.add_argument(
        "--snapshot",
        default=str(DEFAULT_SNAPSHOT_PATH),
        help="Path to snapshot JSON fixture.",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--check",
        action="store_true",
        help="Only report drift; exit 1 if snapshot differs.",
    )
    mode_group.add_argument(
        "--write",
        action="store_true",
        help="Rewrite snapshot fixture. This is the default mode.",
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Print digest contributor paths and rule names.",
    )
    args = parser.parse_args()

    snapshot_path = Path(args.snapshot)
    before = _load_existing(snapshot_path)
    after = build_policy_digest_snapshot()
    changes = _diff_dict(before, after)

    _print_changes(changes)
    if args.explain:
        _print_explain()
    if args.check:
        return 1 if changes else 0

    _write_snapshot(snapshot_path, after)
    print(f"[OK] Wrote snapshot to {snapshot_path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
