"""Inspect or adopt current retained outward inputs after stopping old owners."""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
from pathlib import Path

from orket.application.services.outward_authority_migration_service import OutwardAuthorityMigrationService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--expected-run-digest")
    parser.add_argument("--actor-ref")
    parser.add_argument("--owners-stopped", action="store_true",
                        help="Attest old owners have stopped; the command does not stop or fence old executables.")
    args = parser.parse_args(argv)
    if not args.inspect and (not args.expected_run_digest or not args.actor_ref):
        parser.error("adoption requires --expected-run-digest and --actor-ref")
    try:
        service = OutwardAuthorityMigrationService(args.db)
        operation = service.inspect(args.run_id) if args.inspect else service.migrate(
            args.run_id, expected_run_digest=args.expected_run_digest, actor_ref=args.actor_ref,
            owners_stopped=args.owners_stopped,
        )
        payload = asyncio.run(operation)
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 130
    except (OSError, sqlite3.Error, ValueError, RuntimeError) as exc:
        print(f"Outward authority migration failed for {args.db}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
