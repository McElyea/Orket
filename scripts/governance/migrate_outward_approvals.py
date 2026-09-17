"""Rehearse an offline approval upgrade on a new copy; never replace the active store."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from orket.adapters.storage.outward_approval_upgrade import migrate_outward_approval_copy
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--writers-stopped", action="store_true", required=True)
    parser.add_argument("--out", type=Path, default=Path("benchmarks/staging/outward_approval_migration.json"))
    args = parser.parse_args()
    if args.out.resolve() in {path.resolve() for path in (args.source, args.backup, args.destination)}:
        parser.error("E_OUTWARD_MIGRATION_REPORT_PATH_COLLISION")
    payload = asyncio.run(migrate_outward_approval_copy(
        source=args.source, backup=args.backup, destination=args.destination, writers_stopped=args.writers_stopped,
    ))
    write_payload_with_diff_ledger(args.out, payload)
    print(f"Migrated copy: {args.destination}; legacy dispatch remains disabled. Report: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
