import asyncio
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import aiosqlite

from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from orket.runtime.truthful_memory_policy import (
    classify_memory_trust_level,
    evaluate_memory_write_policy,
    synthesis_disposition_for_trust_level,
)


class MemoryEntry:
    def __init__(self, content: str, metadata: dict[str, Any], timestamp: str) -> None:
        self.content = content
        self.metadata = metadata
        self.timestamp = timestamp


class MemoryStore:
    """
    Persistent Memory Store for Orket (Vector DB Lite).
    Provides RAG capabilities using SQLite and keyword indexing.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._initialized = False
        self._init_lock = asyncio.Lock()

    @staticmethod
    def _keywords_for_content(content: str) -> str:
        terms = sorted({term for term in re.findall(r"[A-Za-z0-9_:-]+", content.lower()) if term})
        return " ".join(terms)

    @staticmethod
    def _fts_query_terms(query: str) -> list[str]:
        return [term for term in re.findall(r"[A-Za-z0-9_:-]+", query.lower()) if term]

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        async with self._init_lock:
            if self._initialized:
                return
            async with connect_sqlite_wal(self.db_path) as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS project_memory (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        content TEXT NOT NULL,
                        metadata_json TEXT NOT NULL,
                        keywords TEXT NOT NULL,
                        content_hash TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                columns_cursor = await conn.execute("PRAGMA table_info(project_memory)")
                columns = {str(row[1]) for row in await columns_cursor.fetchall()}
                if "content_hash" not in columns:
                    await conn.execute("ALTER TABLE project_memory ADD COLUMN content_hash TEXT")
                await conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_project_memory_content_hash "
                    "ON project_memory(content_hash)"
                )
                await conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS project_memory_fts USING fts5(
                        content,
                        keywords
                    )
                """)
                await conn.execute("DELETE FROM project_memory_fts")
                await conn.execute(
                    "INSERT INTO project_memory_fts(rowid, content, keywords) "
                    "SELECT id, content, keywords FROM project_memory"
                )
                await conn.commit()
            self._initialized = True

    async def remember(self, content: str, metadata: dict[str, Any] | None = None) -> None:
        """Stores a new memory."""
        await self._ensure_initialized()
        decision = evaluate_memory_write_policy(
            scope="project_memory",
            key="project_memory",
            value=content,
            metadata=metadata or {},
        )
        metadata = dict(decision.metadata)
        keywords = self._keywords_for_content(content)
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        async with connect_sqlite_wal(self.db_path) as conn:
            existing_cursor = await conn.execute(
                "SELECT id FROM project_memory WHERE content_hash = ?",
                (content_hash,),
            )
            existing = await existing_cursor.fetchone()
            if existing is not None:
                return
            cursor = await conn.execute(
                "INSERT INTO project_memory (content, metadata_json, keywords, content_hash) VALUES (?, ?, ?, ?)",
                (content, json.dumps(metadata), keywords, content_hash),
            )
            memory_id = int(cursor.lastrowid or 0)
            await conn.execute(
                "INSERT INTO project_memory_fts(rowid, content, keywords) VALUES (?, ?, ?)",
                (memory_id, content, keywords),
            )
            await conn.commit()

    async def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Searches memories using SQLite FTS ranking with recency tie-breakers."""
        await self._ensure_initialized()
        query_terms = self._fts_query_terms(query)

        results: list[dict[str, Any]] = []
        async with connect_sqlite_wal(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            if query_terms:
                fts_query = " OR ".join(f'"{term}"' for term in query_terms)
                cursor = await conn.execute(
                    """
                    SELECT pm.*
                    FROM project_memory_fts fts
                    JOIN project_memory pm ON pm.id = fts.rowid
                    WHERE project_memory_fts MATCH ?
                    ORDER BY bm25(project_memory_fts), pm.created_at DESC, pm.id DESC
                    LIMIT ?
                    """,
                    (fts_query, max(1, int(limit))),
                )
            else:
                cursor = await conn.execute(
                    "SELECT * FROM project_memory ORDER BY created_at DESC, id DESC LIMIT ?",
                    (max(1, int(limit)),),
                )
            rows = await cursor.fetchall()

            for row in rows:
                content_words = set(str(row["keywords"] or "").split())
                score = len(set(query_terms).intersection(content_words))
                metadata_payload = json.loads(row["metadata_json"])
                metadata = metadata_payload if isinstance(metadata_payload, dict) else {}
                trust_level = classify_memory_trust_level(
                    scope="project_memory",
                    metadata=metadata,
                    timestamp=str(row["created_at"]),
                )
                results.append(
                    {
                        "content": row["content"],
                        "metadata": metadata,
                        "score": score,
                        "timestamp": row["created_at"],
                        "id": row["id"],
                        "trust_level": trust_level,
                        "synthesis_disposition": synthesis_disposition_for_trust_level(trust_level),
                    }
                )
            return results[: max(1, int(limit))]
