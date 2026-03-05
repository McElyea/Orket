from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage Orket baseline artifacts.")
    sub = parser.add_subparsers(dest="command", required=True)

    list_cmd = sub.add_parser("list", help="List baseline files and latest metadata.")
    list_cmd.add_argument("--storage-root", default=".orket/durable/diagnostics/baselines")
    list_cmd.add_argument("--test-id", default="")

    show_cmd = sub.add_parser("show", help="Show baseline history for one test id.")
    show_cmd.add_argument("--storage-root", default=".orket/durable/diagnostics/baselines")
    show_cmd.add_argument("--test-id", required=True)

    resolve_cmd = sub.add_parser("resolve", help="Resolve latest matching baseline.")
    resolve_cmd.add_argument("--storage-root", default=".orket/durable/diagnostics/baselines")
    resolve_cmd.add_argument("--test-id", required=True)
    resolve_cmd.add_argument("--hardware-fingerprint", required=True)
    resolve_cmd.add_argument("--task-revision", required=True)
    resolve_cmd.add_argument("--baseline-ref", default="")

    pin_cmd = sub.add_parser("pin", help="Pin a baseline ref into a task json acceptance contract.")
    pin_cmd.add_argument("--task-file", required=True)
    pin_cmd.add_argument("--baseline-ref", required=True)

    health_cmd = sub.add_parser("health", help="Compute baseline health summary and stale/incompatibility stats.")
    health_cmd.add_argument("--storage-root", default=".orket/durable/diagnostics/baselines")
    health_cmd.add_argument("--hardware-fingerprint", default="")
    health_cmd.add_argument("--task-revision", default="")

    prune_cmd = sub.add_parser("prune", help="Prune baseline history entries per test id.")
    prune_cmd.add_argument("--storage-root", default=".orket/durable/diagnostics/baselines")
    prune_cmd.add_argument("--test-id", default="")
    prune_cmd.add_argument("--keep-last", type=int, default=0, help="Keep only the newest N records (0 disables prune).")
    prune_cmd.add_argument("--dry-run", action="store_true")

    pin_baseline_cmd = sub.add_parser("pin-baseline", help="Pin a baseline record by test run id.")
    pin_baseline_cmd.add_argument("--storage-root", default=".orket/durable/diagnostics/baselines")
    pin_baseline_cmd.add_argument("--test-id", required=True)
    pin_baseline_cmd.add_argument("--baseline-ref", required=True)

    unpin_baseline_cmd = sub.add_parser("unpin-baseline", help="Unpin a baseline record by test run id.")
    unpin_baseline_cmd.add_argument("--storage-root", default=".orket/durable/diagnostics/baselines")
    unpin_baseline_cmd.add_argument("--test-id", required=True)
    unpin_baseline_cmd.add_argument("--baseline-ref", required=True)

    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _baseline_file(storage_root: Path, test_id: str) -> Path:
    return storage_root / f"{test_id}.json"


def _history(storage_root: Path, test_id: str) -> list[dict[str, Any]]:
    path = _baseline_file(storage_root, test_id)
    if not path.exists():
        return []
    payload = _load_json(path)
    history = payload.get("history")
    if isinstance(history, list):
        return [row for row in history if isinstance(row, dict)]
    return []


def _write_history(storage_root: Path, test_id: str, rows: list[dict[str, Any]]) -> None:
    path = _baseline_file(storage_root, test_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"test_id": test_id, "history": rows}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _sort_history_desc(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def _key(row: dict[str, Any]) -> str:
        meta = row.get("baseline_metadata")
        meta = meta if isinstance(meta, dict) else {}
        return str(meta.get("created_at", ""))

    return sorted(rows, key=_key, reverse=True)


def _cmd_list(args: argparse.Namespace) -> int:
    storage_root = Path(args.storage_root)
    test_filter = str(args.test_id).strip()
    files = sorted(storage_root.glob("*.json")) if storage_root.exists() else []
    rows: list[dict[str, Any]] = []
    for path in files:
        test_id = path.stem
        if test_filter and test_id != test_filter:
            continue
        history = _history(storage_root, test_id)
        latest = _sort_history_desc(history)[0] if history else {}
        meta = latest.get("baseline_metadata") if isinstance(latest, dict) else {}
        meta = meta if isinstance(meta, dict) else {}
        rows.append(
            {
                "test_id": test_id,
                "history_count": len(history),
                "pinned_count": len(
                    [
                        row
                        for row in history
                        if bool((row.get("baseline_metadata") or {}).get("pinned", False))
                    ]
                ),
                "latest_test_run_id": str(meta.get("test_run_id", "")),
                "latest_created_at": str(meta.get("created_at", "")),
                "latest_hardware_fingerprint": str(meta.get("hardware_fingerprint", "")),
                "latest_task_revision": str(meta.get("task_revision", "")),
            }
        )
    print(json.dumps({"generated_at": datetime.now(UTC).isoformat(), "items": rows}, indent=2))
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    storage_root = Path(args.storage_root)
    test_id = str(args.test_id).strip()
    rows = _sort_history_desc(_history(storage_root, test_id))
    print(json.dumps({"test_id": test_id, "history": rows}, indent=2))
    return 0


def _cmd_resolve(args: argparse.Namespace) -> int:
    storage_root = Path(args.storage_root)
    test_id = str(args.test_id).strip()
    hardware = str(args.hardware_fingerprint).strip()
    task_revision = str(args.task_revision).strip()
    baseline_ref = str(args.baseline_ref).strip()

    history = _history(storage_root, test_id)
    if not history:
        print(json.dumps({"status": "NO_BASELINE", "record": None}, indent=2))
        return 0
    hw_matches = [
        row
        for row in history
        if str((row.get("baseline_metadata") or {}).get("hardware_fingerprint", "")).strip() == hardware
    ]
    if not hw_matches:
        print(json.dumps({"status": "HW_MISMATCH", "record": None}, indent=2))
        return 0
    rev_matches = [
        row
        for row in hw_matches
        if str((row.get("baseline_metadata") or {}).get("task_revision", "")).strip() == task_revision
    ]
    if not rev_matches:
        print(json.dumps({"status": "REV_MISMATCH", "record": None}, indent=2))
        return 0
    if baseline_ref:
        ref_matches = [
            row
            for row in rev_matches
            if str((row.get("baseline_metadata") or {}).get("test_run_id", "")).strip() == baseline_ref
        ]
        if ref_matches:
            rev_matches = ref_matches
    resolved = _sort_history_desc(rev_matches)[0]
    print(json.dumps({"status": "OK", "record": resolved}, indent=2))
    return 0


def _cmd_pin(args: argparse.Namespace) -> int:
    task_path = Path(args.task_file)
    payload = _load_json(task_path)
    acceptance = payload.get("acceptance_contract")
    if not isinstance(acceptance, dict):
        acceptance = {}
        payload["acceptance_contract"] = acceptance
    acceptance["baseline_ref"] = str(args.baseline_ref).strip()
    task_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "OK", "task_file": str(task_path).replace("\\", "/"), "baseline_ref": acceptance["baseline_ref"]}, indent=2))
    return 0


def _cmd_health(args: argparse.Namespace) -> int:
    storage_root = Path(args.storage_root)
    hardware = str(args.hardware_fingerprint).strip()
    task_revision = str(args.task_revision).strip()
    files = sorted(storage_root.glob("*.json")) if storage_root.exists() else []

    tests_total = 0
    records_total = 0
    stale_total = 0
    incompatible_hardware_total = 0
    incompatible_revision_total = 0
    per_test: list[dict[str, Any]] = []
    for file_path in files:
        test_id = file_path.stem
        rows = _sort_history_desc(_history(storage_root, test_id))
        tests_total += 1
        records_total += len(rows)
        if len(rows) > 1:
            stale_total += len(rows) - 1

        hw_mismatch = 0
        rev_mismatch = 0
        for row in rows:
            meta = row.get("baseline_metadata") if isinstance(row, dict) else {}
            meta = meta if isinstance(meta, dict) else {}
            row_hw = str(meta.get("hardware_fingerprint", "")).strip()
            row_rev = str(meta.get("task_revision", "")).strip()
            if hardware and row_hw != hardware:
                hw_mismatch += 1
            if task_revision and row_rev != task_revision:
                rev_mismatch += 1
        incompatible_hardware_total += hw_mismatch
        incompatible_revision_total += rev_mismatch
        per_test.append(
            {
                "test_id": test_id,
                "records": len(rows),
                "stale_records": max(0, len(rows) - 1),
                "hardware_mismatch_records": hw_mismatch,
                "revision_mismatch_records": rev_mismatch,
            }
        )

    print(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "storage_root": str(storage_root).replace("\\", "/"),
                "scope": {
                    "hardware_fingerprint": hardware,
                    "task_revision": task_revision,
                },
                "summary": {
                    "tests_total": tests_total,
                    "records_total": records_total,
                    "stale_records_total": stale_total,
                    "hardware_mismatch_records_total": incompatible_hardware_total,
                    "revision_mismatch_records_total": incompatible_revision_total,
                },
                "per_test": per_test,
            },
            indent=2,
        )
    )
    return 0


def _cmd_prune(args: argparse.Namespace) -> int:
    storage_root = Path(args.storage_root)
    keep_last = int(args.keep_last)
    if keep_last <= 0:
        print(json.dumps({"status": "NOOP", "reason": "keep_last must be > 0"}, indent=2))
        return 0

    files = sorted(storage_root.glob("*.json")) if storage_root.exists() else []
    test_filter = str(args.test_id).strip()
    modified: list[dict[str, Any]] = []
    for file_path in files:
        test_id = file_path.stem
        if test_filter and test_id != test_filter:
            continue
        rows = _sort_history_desc(_history(storage_root, test_id))
        if len(rows) <= keep_last:
            continue
        pinned_rows = [row for row in rows if bool((row.get("baseline_metadata") or {}).get("pinned", False))]
        unpinned_rows = [row for row in rows if not bool((row.get("baseline_metadata") or {}).get("pinned", False))]
        kept = pinned_rows + unpinned_rows[:keep_last]
        removed = len(rows) - len(kept)
        if removed <= 0:
            continue
        modified.append({"test_id": test_id, "removed": removed, "remaining": len(kept)})
        if args.dry_run:
            continue
        _write_history(storage_root, test_id, _sort_history_desc(kept))

    print(
        json.dumps(
            {
                "status": "OK",
                "dry_run": bool(args.dry_run),
                "keep_last": keep_last,
                "modified": modified,
            },
            indent=2,
        )
    )
    return 0


def _cmd_pin_baseline(args: argparse.Namespace) -> int:
    storage_root = Path(args.storage_root)
    test_id = str(args.test_id).strip()
    baseline_ref = str(args.baseline_ref).strip()
    rows = _history(storage_root, test_id)
    if not rows:
        print(json.dumps({"status": "NO_BASELINE", "test_id": test_id, "baseline_ref": baseline_ref}, indent=2))
        return 0
    updated = False
    for row in rows:
        meta = row.get("baseline_metadata")
        meta = meta if isinstance(meta, dict) else {}
        if str(meta.get("test_run_id", "")).strip() == baseline_ref:
            meta["pinned"] = True
            row["baseline_metadata"] = meta
            updated = True
    if not updated:
        print(json.dumps({"status": "BASELINE_REF_NOT_FOUND", "test_id": test_id, "baseline_ref": baseline_ref}, indent=2))
        return 0
    _write_history(storage_root, test_id, rows)
    print(json.dumps({"status": "OK", "test_id": test_id, "baseline_ref": baseline_ref, "pinned": True}, indent=2))
    return 0


def _cmd_unpin_baseline(args: argparse.Namespace) -> int:
    storage_root = Path(args.storage_root)
    test_id = str(args.test_id).strip()
    baseline_ref = str(args.baseline_ref).strip()
    rows = _history(storage_root, test_id)
    if not rows:
        print(json.dumps({"status": "NO_BASELINE", "test_id": test_id, "baseline_ref": baseline_ref}, indent=2))
        return 0
    updated = False
    for row in rows:
        meta = row.get("baseline_metadata")
        meta = meta if isinstance(meta, dict) else {}
        if str(meta.get("test_run_id", "")).strip() == baseline_ref:
            meta["pinned"] = False
            row["baseline_metadata"] = meta
            updated = True
    if not updated:
        print(json.dumps({"status": "BASELINE_REF_NOT_FOUND", "test_id": test_id, "baseline_ref": baseline_ref}, indent=2))
        return 0
    _write_history(storage_root, test_id, rows)
    print(json.dumps({"status": "OK", "test_id": test_id, "baseline_ref": baseline_ref, "pinned": False}, indent=2))
    return 0


def main() -> int:
    args = _parse_args()
    if args.command == "list":
        return _cmd_list(args)
    if args.command == "show":
        return _cmd_show(args)
    if args.command == "resolve":
        return _cmd_resolve(args)
    if args.command == "pin":
        return _cmd_pin(args)
    if args.command == "health":
        return _cmd_health(args)
    if args.command == "prune":
        return _cmd_prune(args)
    if args.command == "pin-baseline":
        return _cmd_pin_baseline(args)
    if args.command == "unpin-baseline":
        return _cmd_unpin_baseline(args)
    raise SystemExit(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
