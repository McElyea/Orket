"""Serialize supported workspace writes with final card evidence inspection."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

from orket.adapters.execution.owned_io import run_owned_io
from orket.core.contracts.repositories import CardRepository

MutationResult = TypeVar("MutationResult")


class CardWorkspaceMutationService:
    def __init__(self, cards: CardRepository):
        self.cards = cards

    async def run(self, operation: Callable[[], Awaitable[MutationResult]]) -> MutationResult:
        async def owned_write() -> MutationResult:
            async with self.cards.completion_write_guard():
                return await operation()

        return await run_owned_io(owned_write, label="card-workspace-mutation", preserve_failure=True)
