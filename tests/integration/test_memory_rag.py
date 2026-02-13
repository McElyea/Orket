import pytest
import asyncio
from pathlib import Path
from orket.services.memory_store import MemoryStore

@pytest.mark.asyncio
async def test_memory_store_retrieval(tmp_path):
    db_path = tmp_path / "memory.db"
    store = MemoryStore(db_path)
    
    await store.remember("Use PostgreSQL for all persistence.", {"type": "decision"})
    await store.remember("Standardize on FastAPI for backend services.", {"type": "standard"})
    
    # Search by keyword
    results = await store.search("FastAPI")
    assert len(results) >= 1
    assert "FastAPI" in results[0]["content"]
    
    # Search by multiple keywords
    results = await store.search("PostgreSQL persistence")
    assert len(results) >= 1
    assert "PostgreSQL" in results[0]["content"]

@pytest.mark.asyncio
async def test_memory_store_recency(tmp_path):
    db_path = tmp_path / "memory.db"
    store = MemoryStore(db_path)
    
    await store.remember("Old decision")
    await asyncio.sleep(0.1)
    await store.remember("New decision")
    
    results = await store.search("") # Empty query = recent
    assert results[0]["content"] == "New decision"

