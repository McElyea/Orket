"""Native project memory effects; application owns inputs, policy and invocation lifetime."""

from __future__ import annotations

from functools import partial
from pathlib import Path

import aiosqlite

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.sqlite_connection import connect_sqlite_wal

side_effecting = True


class ProjectMemoryRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    async def initialize(self):
        await run_owned_thread(
            partial(self.db_path.parent.mkdir, parents=True, exist_ok=True), label="project-memory directory"
        )
        async with connect_sqlite_wal(self.db_path) as connection:
            await connection.execute("BEGIN IMMEDIATE")
            await connection.execute("""
                CREATE TABLE IF NOT EXISTS project_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    keywords TEXT NOT NULL,
                    content_hash TEXT,
                    created_at DATETIME NOT NULL
                )
            """)
            async with connection.execute("PRAGMA table_info(project_memory)") as cursor:
                columns = {str(row[1]) for row in await cursor.fetchall()}
            if "content_hash" not in columns:
                await connection.execute("ALTER TABLE project_memory ADD COLUMN content_hash TEXT")
            await connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_project_memory_content_hash ON project_memory(content_hash)"
            )
            await connection.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS project_memory_fts USING fts5(content, keywords)"
            )
            await connection.execute("DELETE FROM project_memory_fts")
            await connection.execute(
                "INSERT INTO project_memory_fts(rowid, content, keywords) "
                "SELECT id, content, keywords FROM project_memory"
            )
            await connection.commit()

    async def remember(self, *, content, metadata_json, keywords, content_hash, timestamp):
        async with connect_sqlite_wal(self.db_path) as connection:
            await connection.execute("BEGIN IMMEDIATE")
            async with connection.execute(
                "SELECT id FROM project_memory WHERE content_hash=?", (content_hash,)
            ) as cursor:
                existing = await cursor.fetchone()
            if existing is not None:
                return
            async with connection.execute(
                "INSERT INTO project_memory (content, metadata_json, keywords, content_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                (content, metadata_json, keywords, content_hash, timestamp),
            ) as cursor:
                memory_id = int(cursor.lastrowid)
            await connection.execute(
                "INSERT INTO project_memory_fts(rowid, content, keywords) VALUES (?, ?, ?)",
                (memory_id, content, keywords),
            )
            await connection.commit()

    async def search(self, *, query_terms, limit):
        async with connect_sqlite_wal(self.db_path) as connection:
            connection.row_factory = aiosqlite.Row
            if query_terms:
                sql = """
                    SELECT pm.* FROM project_memory_fts fts
                    JOIN project_memory pm ON pm.id = fts.rowid
                    WHERE project_memory_fts MATCH ?
                    ORDER BY bm25(project_memory_fts), pm.created_at DESC, pm.id DESC LIMIT ?
                """
                args = (" OR ".join(f'"{term}"' for term in query_terms), limit)
            else:
                sql, args = "SELECT * FROM project_memory ORDER BY created_at DESC, id DESC LIMIT ?", (limit,)
            async with connection.execute(sql, args) as cursor:
                return [dict(row) for row in await cursor.fetchall()]
