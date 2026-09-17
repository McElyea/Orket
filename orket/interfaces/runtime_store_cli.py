"""Installed offline entrypoint for the declared relative-store migration."""

from __future__ import annotations

import argparse
import asyncio
import sqlite3
import sys
from pathlib import Path

from orket.application.services.runtime_store_migration_service import RuntimeStoreMigrationService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-db", type=Path, required=True)
    parser.add_argument("--legacy-control-plane-db", type=Path, required=True)
    parser.add_argument("--legacy-invocation-root", type=Path, required=True)
    parser.add_argument("--actor-ref", required=True)
    parser.add_argument(
        "--owners-stopped",
        action="store_true",
        help="Confirm that old runtime owners have been stopped; this command does not stop them.",
    )
    args = parser.parse_args(argv)
    try:
        service = RuntimeStoreMigrationService(
            args.runtime_db,
            legacy_control_plane_db=args.legacy_control_plane_db,
            legacy_invocation_root=args.legacy_invocation_root,
        )
        binding = asyncio.run(service.migrate(actor_ref=args.actor_ref, owners_stopped=args.owners_stopped))
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 130
    except (OSError, sqlite3.Error, ValueError) as exc:
        print(f"Runtime store migration command failed for {args.runtime_db}: {exc}", file=sys.stderr)
        return 1
    print(f"Runtime store binding retained: {binding.digest()}")
    print(f"Runtime: {binding.runtime_db}\nControl plane: {binding.control_plane_db}")
    print(f"Preserved session scopes: {len(binding.sessions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
