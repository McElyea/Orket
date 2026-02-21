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
    list_cmd.add_argument("--storage-root", default="orket_storage/baselines")
    list_cmd.add_argument("--test-id", default="")

    show_cmd = sub.add_parser("show", help="Show baseline history for one test id.")
    show_cmd.add_argument("--storage-root", default="orket_storage/baselines")
    show_cmd.add_argument("--test-id", required=True)

    resolve_cmd = sub.add_parser("resolve", help="Resolve latest matching baseline.")
    resolve_cmd.add_argument("--storage-root", default="orket_storage/baselines")
    resolve_cmd.add_argument("--test-id", required=True)
    resolve_cmd.add_argument("--hardware-fingerprint", required=True)
    resolve_cmd.add_argument("--task-revision", required=True)
    resolve_cmd.add_argument("--baseline-ref", default="")

    pin_cmd = sub.add_parser("pin", help="Pin a baseline ref into a task json acceptance contract.")
    pin_cmd.add_argument("--task-file", required=True)
    pin_cmd.add_argument("--baseline-ref", required=True)

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
    raise SystemExit(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
