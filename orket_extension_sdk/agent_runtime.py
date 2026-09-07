from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from .agent_models import (
    AgentIterationRequest,
    AgentIterationResult,
    AgentMemoryQueryRequest,
    AgentMemoryQueryResult,
    AgentModelCallRequest,
    AgentModelCallResult,
)
from .agent_types import AgentCancellation, AgentIdentity, AgentProgress


class AgentModelCapability(Protocol):
    async def call(self, request: AgentModelCallRequest) -> AgentModelCallResult: ...


class AgentMemoryCapability(Protocol):
    async def query(self, request: AgentMemoryQueryRequest) -> AgentMemoryQueryResult: ...


class AgentCancellationView:
    """Read-only workload view updated only by the SDK's host protocol handler."""

    def __init__(self, initial: AgentCancellation) -> None:
        self._snapshot = initial
        self._event = asyncio.Event()
        if initial.requested:
            self._event.set()

    def snapshot(self) -> AgentCancellation:
        return self._snapshot

    async def wait(self) -> AgentCancellation:
        await self._event.wait()
        return self._snapshot

    def _apply_host_cancellation(self, value: AgentCancellation) -> None:
        if value.cancellation_epoch <= self._snapshot.cancellation_epoch:
            raise ValueError("E_SDK_AGENT_CANCELLATION_EPOCH_STALE")
        self._snapshot = value
        if value.requested:
            self._event.set()


class AgentProgressReporter:
    def __init__(
        self,
        *,
        identity: AgentIdentity,
        maximum_events: int,
        publish: Callable[[AgentProgress], Awaitable[None]],
    ) -> None:
        if maximum_events < 0:
            raise ValueError("E_SDK_AGENT_PROGRESS_LIMIT_INVALID")
        self._identity = identity
        self._maximum_events = maximum_events
        self._publish = publish
        self._sequence = 0

    async def report(self, *, summary: str, evidence_refs: tuple[str, ...] = ()) -> AgentProgress:
        if self._sequence >= self._maximum_events:
            raise ValueError("E_SDK_AGENT_PROGRESS_LIMIT_EXCEEDED")
        progress = AgentProgress(
            identity=self._identity,
            sequence=self._sequence + 1,
            summary=summary,
            evidence_refs=evidence_refs,
        )
        await asyncio.to_thread(progress.to_wire)
        await self._publish(progress)
        self._sequence += 1
        return progress


@dataclass(frozen=True, slots=True)
class AgentWorkloadContext:
    request: AgentIterationRequest
    model: AgentModelCapability
    memory: AgentMemoryCapability
    cancellation: AgentCancellationView
    progress: AgentProgressReporter


class AsyncAgentWorkload(Protocol):
    async def run(self, context: AgentWorkloadContext) -> AgentIterationResult: ...
