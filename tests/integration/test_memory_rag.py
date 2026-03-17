import asyncio
from pathlib import Path

import pytest

from orket.runtime.truthful_memory_policy import render_reference_context_rows
from orket.services.memory_store import MemoryStore


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
    rendered = render_reference_context_rows(results)
    assert "Fresh durable note" in rendered
    assert "Stale note" not in rendered
