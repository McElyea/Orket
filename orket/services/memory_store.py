import json
import aiosqlite
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, UTC

class MemoryEntry:
    def __init__(self, content: str, metadata: Dict[str, Any], timestamp: str):
        self.content = content
        self.metadata = metadata
        self.timestamp = timestamp

class MemoryStore:
    """
    Persistent Memory Store for Orket (Vector DB Lite).
    Provides RAG capabilities using SQLite and keyword indexing.
    """
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._initialized = False

    async def _ensure_initialized(self):
        if self._initialized: return
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

    async def remember(self, content: str, metadata: Dict[str, Any] = None):
        """Stores a new memory."""
        await self._ensure_initialized()
        metadata = metadata or {}
        # Simple keyword extraction: lowercasing and splitting
        keywords = " ".join(set(content.lower().split()))
        
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "INSERT INTO project_memory (content, metadata_json, keywords) VALUES (?, ?, ?)",
                (content, json.dumps(metadata), keywords)
            )
            await conn.commit()

    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Searches memories using simple keyword matching."""
        await self._ensure_initialized()
        query_words = set(query.lower().split())
        
        results = []
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            # Use id for tie-breaking on same timestamp
            cursor = await conn.execute("SELECT * FROM project_memory ORDER BY created_at DESC, id DESC")
            rows = await cursor.fetchall()
            
            for row in rows:
                content_words = set(row['keywords'].split())
                score = len(query_words.intersection(content_words))
                if score > 0 or not query: # Return recent if no query or matches
                    results.append({
                        "content": row['content'],
                        "metadata": json.loads(row['metadata_json']),
                        "score": score,
                        "timestamp": row['created_at'],
                        "id": row['id']
                    })
            
            # Sort by score then ID (recency)
            results.sort(key=lambda x: (x['score'], x['id']), reverse=True)
            return results[:limit]
