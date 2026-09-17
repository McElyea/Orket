"""Validate legacy ledger history and import only a new, inactive SQLite copy."""

from __future__ import annotations

import argparse
import asyncio
import sqlite3
from pathlib import Path

from orket.adapters.storage.outward_ledger_upgrade import migrate_outward_ledger_copy
from orket.adapters.storage.sqlite_backup import sqlite_files
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger


def _validate_report_path(parser, args) -> None:
    report = args.out.resolve()
    for path in (*sqlite_files(args.source), *sqlite_files(args.backup), *sqlite_files(args.destination)):
        resolved = path.resolve()
        if report == resolved or (report.exists() and resolved.exists() and report.samefile(resolved)):
            parser.error("E_OUTWARD_MIGRATION_REPORT_PATH_COLLISION")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--writers-stopped", action="store_true", required=True)
    parser.add_argument("--allow-unsealed", action="store_true")
    parser.add_argument("--out", type=Path, default=Path("benchmarks/staging/outward_ledger_migration.json"))
    args = parser.parse_args()
    _validate_report_path(parser, args)
    status = {
        "schema_version": "outward_ledger_migration.v2", "state": "started", "observed_path": "primary",
        "observed_result": "partial success", "candidate_activated": False, "authenticity": "not_established",
        "source": str(args.source.resolve()), "backup": str(args.backup.resolve()),
        "destination": str(args.destination.resolve()),
    }
    # Invalidate an earlier successful report before copying; a killed process leaves "started".
    write_payload_with_diff_ledger(args.out, status)
    try:
        payload = asyncio.run(migrate_outward_ledger_copy(
            source=args.source, backup=args.backup, destination=args.destination,
            writers_stopped=args.writers_stopped, allow_unsealed=args.allow_unsealed,
        ))
    except (OSError, ValueError, sqlite3.DatabaseError) as exc:
        write_payload_with_diff_ledger(args.out, {
            **status, "state": "failed", "observed_result": "failure", "error": str(exc),
            "candidate_disposition": "unverified_do_not_activate",
        })
        print(f"Ledger import failed: {exc}. Retain all copies; retry with new output paths. Report: {args.out}")
        return 1
    write_payload_with_diff_ledger(args.out, {
        **status, **payload, "state": "complete", "observed_result": "success",
    })
    print(f"Verified copy: {args.destination}. Execution authority unchanged; candidate inactive. Report: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
