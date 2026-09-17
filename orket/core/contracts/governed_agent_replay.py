from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class GovernedAgentReplayEvidence:
    """One database snapshot; control-plane steps supply the expected inventory."""

    run: Mapping[str, Any] | None = None
    attempts: tuple[Mapping[str, Any], ...] = ()
    steps: tuple[Mapping[str, Any], ...] = ()
    iterations: tuple[Mapping[str, Any], ...] = ()
    final_truth: Mapping[str, Any] | None = None
    diagnostics: tuple[str, ...] = ()


class GovernedAgentReplayRepository(Protocol):
    async def read_replay_evidence(self, *, run_id: str) -> GovernedAgentReplayEvidence:
        """Read a consistent snapshot without initializing or modifying the store."""
        ...
