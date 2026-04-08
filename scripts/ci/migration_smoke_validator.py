from __future__ import annotations

import argparse
import asyncio
import sqlite3
import sys
from pathlib import Path

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.adapters.vcs.webhook_db import WebhookDatabase


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap or validate runtime/webhook migration smoke databases.")
    parser.add_argument("--runtime-db", default=".ci/runtime.db")
    parser.add_argument("--webhook-db", default=".ci/webhook.db")
    parser.add_argument("--bootstrap", action="store_true", help="Create runtime and webhook schemas through live repositories.")
    parser.add_argument("--validate", action="store_true", help="Require migration ledger rows in both databases.")
    return parser


async def _bootstrap(runtime_db: Path, webhook_db: Path) -> None:
    runtime_db.parent.mkdir(parents=True, exist_ok=True)
    webhook_db.parent.mkdir(parents=True, exist_ok=True)
    repo = AsyncCardRepository(str(runtime_db))
    await repo.get_by_build("_migration_smoke_bootstrap_")
    webhook = WebhookDatabase(webhook_db)
    await webhook.get_active_prs()


def _migration_count(path: Path) -> int:
    connection = sqlite3.connect(path)
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM _schema_migrations")
        return int(cursor.fetchone()[0])
    finally:
        connection.close()


def _validate(runtime_db: Path, webhook_db: Path) -> None:
    for db_path in (runtime_db, webhook_db):
        if _migration_count(db_path) < 1:
            raise RuntimeError(f"No migrations recorded for {db_path}")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    runtime_db = Path(str(args.runtime_db))
    webhook_db = Path(str(args.webhook_db))
    if not bool(args.bootstrap) and not bool(args.validate):
        raise SystemExit("Specify --bootstrap, --validate, or both.")
    if bool(args.bootstrap):
        asyncio.run(_bootstrap(runtime_db=runtime_db, webhook_db=webhook_db))
        print("Schema bootstrap completed")
    if bool(args.validate):
        _validate(runtime_db=runtime_db, webhook_db=webhook_db)
        print("Migration smoke validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
