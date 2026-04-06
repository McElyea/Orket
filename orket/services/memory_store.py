import json
from pathlib import Path
from typing import Any

import aiosqlite

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

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS project_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT,
                    metadata_json TEXT,
                    keywords TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
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
        # Simple keyword extraction: lowercasing and splitting
        keywords = " ".join(set(content.lower().split()))

        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "INSERT INTO project_memory (content, metadata_json, keywords) VALUES (?, ?, ?)",
                (content, json.dumps(metadata), keywords),
            )
            await conn.commit()

    async def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Searches memories using simple keyword matching."""
        await self._ensure_initialized()
        query_words = set(query.lower().split())

        results: list[dict[str, Any]] = []
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            # Use id for tie-breaking on same timestamp
            cursor = await conn.execute(
                "SELECT * FROM project_memory ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit * 20,),
            )
            rows = await cursor.fetchall()

            for row in rows:
                content_words = set(row["keywords"].split())
                score = len(query_words.intersection(content_words))
                if score > 0 or not query:  # Return recent if no query or matches
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

            # Sort by score then ID (recency)
            results.sort(key=lambda x: (x["score"], x["id"]), reverse=True)
            return results[:limit]
