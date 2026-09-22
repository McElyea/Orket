"""Application ownership of captured project memory inputs and SQLite lifetime."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from copy import deepcopy
from functools import partial
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_io
from orket.adapters.storage.async_file_tools import capture_file_roots
from orket.adapters.storage.project_memory_repository import ProjectMemoryRepository
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.core.contracts.memory_inputs import memory_observation_time, memory_timestamp
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
    def __init__(self, db_path: str | Path, *, runtime_inputs: RuntimeInputService | None = None) -> None:
        (captured_path,) = capture_file_roots([Path(db_path)])
        self._repository = ProjectMemoryRepository(captured_path)
        self._runtime_inputs = RuntimeInputService() if runtime_inputs is None else runtime_inputs
        self._initialized = False
        self._init_lock = asyncio.Lock()

    @property
    def db_path(self) -> str:
        return str(self._repository.db_path)

    @staticmethod
    def _keywords_for_content(content: str) -> str:
        terms = sorted({term for term in re.findall(r"[A-Za-z0-9_:-]+", content.lower()) if term})
        return " ".join(terms)

    @staticmethod
    def _fts_query_terms(query: str) -> list[str]:
        return [term for term in re.findall(r"[A-Za-z0-9_:-]+", query.lower()) if term]

    async def _ensure_initialized(self) -> None:
        await run_owned_io(self._initialize, label="project-memory initialization", preserve_failure=True)

    async def _initialize(self) -> None:
        if self._initialized:
            return
        async with self._init_lock:
            if not self._initialized:
                await self._repository.initialize()
                self._initialized = True

    async def remember(self, content: str, metadata: dict[str, Any] | None = None) -> None:
        decision = evaluate_memory_write_policy(
            scope="project_memory", key="project_memory", value=content, metadata=deepcopy(metadata or {})
        )
        captured = dict(
            content=content,
            metadata_json=json.dumps(decision.metadata),
            keywords=self._keywords_for_content(content),
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            timestamp=memory_timestamp(self._runtime_inputs.utc_now()),
        )
        await run_owned_io(partial(self._remember, captured), label="project-memory write", preserve_failure=True)

    async def _remember(self, captured) -> None:
        await self._ensure_initialized()
        await self._repository.remember(**captured)

    async def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        query_terms, bounded_limit = self._fts_query_terms(query), max(1, int(limit))
        observed_at = memory_observation_time(self._runtime_inputs.utc_now())
        await self._ensure_initialized()
        rows = await run_owned_io(
            partial(self._repository.search, query_terms=query_terms, limit=bounded_limit),
            label="project-memory search",
            preserve_failure=True,
        )
        results = []
        for row in rows:
            content_words = set(str(row["keywords"] or "").split())
            metadata_payload = json.loads(row["metadata_json"])
            metadata = metadata_payload if isinstance(metadata_payload, dict) else {}
            trust_level = classify_memory_trust_level(
                scope="project_memory", metadata=metadata, timestamp=str(row["created_at"]), observed_at=observed_at
            )
            results.append(
                dict(
                    content=row["content"],
                    metadata=metadata,
                    score=len(set(query_terms).intersection(content_words)),
                    timestamp=row["created_at"],
                    id=row["id"],
                    trust_level=trust_level,
                    synthesis_disposition=synthesis_disposition_for_trust_level(trust_level),
                )
            )
        return results[:bounded_limit]
