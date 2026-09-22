import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from orket.adapters.storage import sqlite_connection
from orket.runtime.truthful_memory_policy import render_reference_context_rows
from orket.services.memory_store import MemoryStore

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_memory_store_retrieval(tmp_path: Path):
    """Layer: integration. Verifies project-memory keyword retrieval still returns matching reference context."""
    db_path = tmp_path / "memory.db"
    store = MemoryStore(db_path)

    await store.remember("Use PostgreSQL for all persistence.", {"type": "decision"})
    await store.remember("Standardize on FastAPI for backend services.", {"type": "standard"})

    results = await store.search("FastAPI")
    assert len(results) >= 1
    assert "FastAPI" in results[0]["content"]

    results = await store.search("PostgreSQL persistence")
    assert len(results) >= 1
    assert "PostgreSQL" in results[0]["content"]


@pytest.mark.asyncio
async def test_memory_store_recency(tmp_path: Path):
    """Layer: integration. Verifies empty-query project-memory retrieval preserves recency ordering."""
    db_path = tmp_path / "memory.db"
    store = MemoryStore(db_path)

    await store.remember("Old decision")
    await asyncio.sleep(0.1)
    await store.remember("New decision")

    results = await store.search("")
    assert results[0]["content"] == "New decision"


@pytest.mark.asyncio
async def test_memory_store_search_exposes_trust_and_filters_stale_context_rendering(tmp_path: Path):
    """Layer: integration. Verifies project-memory search exposes trust metadata and excludes stale context from governed rendering."""
    db_path = tmp_path / "memory.db"
    store = MemoryStore(db_path)

    await store.remember("Fresh durable note", {"type": "decision"})
    await store.remember("Stale note", {"type": "decision", "stale_at": "2000-01-01T00:00:00+00:00"})

    results = await store.search("note", limit=10)
    assert any(row["trust_level"] == "advisory" for row in results)
    rendered = render_reference_context_rows(results, observed_at=datetime.now(UTC))
    assert "Fresh durable note" in rendered
    assert "Stale note" not in rendered


@pytest.mark.asyncio
async def test_memory_store_initializes_once_under_concurrent_calls(monkeypatch, tmp_path: Path) -> None:
    """Layer: integration. Concurrent first use initializes one real SQLite connection."""
    connects = {"count": 0}
    original_connect = sqlite_connection.aiosqlite.connect

    def _connect(*args, **kwargs):
        connects["count"] += 1
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite_connection.aiosqlite, "connect", _connect)
    store = MemoryStore(tmp_path / "memory.db")

    await asyncio.gather(store._ensure_initialized(), store._ensure_initialized(), store._ensure_initialized())

    assert connects["count"] == 1
    await store.remember("Concurrent initialization preserves searchable records.")
    rows = await store.search("searchable")
    assert len(rows) == 1
    assert rows[0]["content"] == "Concurrent initialization preserves searchable records."


@pytest.mark.asyncio
async def test_memory_store_deduplicates_duplicate_content(tmp_path: Path) -> None:
    """Layer: integration. Verifies repeated content writes are ignored through the content-hash guard."""
    store = MemoryStore(tmp_path / "memory.db")

    await store.remember("Use PostgreSQL for all persistence.", {"type": "decision"})
    await store.remember("Use PostgreSQL for all persistence.", {"type": "decision"})

    results = await store.search("PostgreSQL", limit=10)

    assert len(results) == 1
