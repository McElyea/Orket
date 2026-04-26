from __future__ import annotations

from dataclasses import dataclass

import aiosqlite


@dataclass(frozen=True)
class SQLiteMigration:
    version: int
    name: str
    statements: tuple[str, ...]


class SQLiteMigrationRunner:
    def __init__(self, *, namespace: str) -> None:
        self.namespace = str(namespace or "").strip()
        if not self.namespace:
            raise ValueError("migration namespace is required")

    async def apply(self, conn: aiosqlite.Connection, migrations: list[SQLiteMigration]) -> None:
        await self._ensure_table(conn)
        applied = await self.applied_versions(conn)
        for migration in sorted(migrations, key=lambda item: item.version):
            version = int(migration.version)
            if version in applied:
                continue
            if version <= 0:
                raise ValueError("migration version must be positive")
            for statement in migration.statements:
                token = str(statement or "").strip()
                if token:
                    await conn.execute(token)
            await conn.execute(
                """
                INSERT INTO schema_migrations (namespace, version, name)
                VALUES (?, ?, ?)
                """,
                (self.namespace, version, str(migration.name or "")),
            )
            applied.add(version)

    async def applied_versions(self, conn: aiosqlite.Connection) -> set[int]:
        await self._ensure_table(conn)
        cursor = await conn.execute(
            "SELECT version FROM schema_migrations WHERE namespace = ?",
            (self.namespace,),
        )
        rows = await cursor.fetchall()
        return {int(row[0]) for row in rows}

    @staticmethod
    async def _ensure_table(conn: aiosqlite.Connection) -> None:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                namespace TEXT NOT NULL,
                version INTEGER NOT NULL,
                name TEXT NOT NULL,
                applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(namespace, version)
            )
            """
        )


__all__ = ["SQLiteMigration", "SQLiteMigrationRunner"]
