from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, UTC
from pathlib import Path


def _ensure_meta(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS _schema_migrations (
            id TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def _applied(conn: sqlite3.Connection) -> set[str]:
    _ensure_meta(conn)
    rows = conn.execute("SELECT id FROM _schema_migrations").fetchall()
    return {row[0] for row in rows}


def apply_sql_migration(conn: sqlite3.Connection, migration_path: Path) -> bool:
    migration_id = migration_path.name
    applied = _applied(conn)
    if migration_id in applied:
        return False

    sql = migration_path.read_text(encoding="utf-8")
    with conn:
        conn.executescript(sql)
        conn.execute(
            "INSERT INTO _schema_migrations (id, applied_at) VALUES (?, ?)",
            (migration_id, datetime.now(UTC).isoformat()),
        )
    return True


def run(db_path: Path, migration_dir: Path, target: str) -> tuple[int, int]:
    migration_files = sorted(
        p for p in migration_dir.glob("*.sql")
        if f"_{target}_" in p.name
    )
    if not migration_files:
        return 0, 0

    db_path.parent.mkdir(parents=True, exist_ok=True)
    applied_count = 0
    with sqlite3.connect(db_path) as conn:
        for migration in migration_files:
            changed = apply_sql_migration(conn, migration)
            if changed:
                applied_count += 1
                print(f"[MIGRATE] Applied {migration.name} to {db_path}")
            else:
                print(f"[MIGRATE] Skipped {migration.name} (already applied) on {db_path}")
    return applied_count, len(migration_files)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Orket SQLite schema migrations.")
    parser.add_argument("--runtime-db", default="orket_persistence.db")
    parser.add_argument("--webhook-db", default=".orket/webhook.db")
    parser.add_argument("--migration-dir", default="scripts/migrations")
    args = parser.parse_args()

    migration_dir = Path(args.migration_dir)
    if not migration_dir.exists():
        raise SystemExit(f"Migration directory not found: {migration_dir}")

    runtime_db = Path(args.runtime_db)
    webhook_db = Path(args.webhook_db)

    run(runtime_db, migration_dir, target="runtime")
    run(webhook_db, migration_dir, target="webhook")


if __name__ == "__main__":
    main()
