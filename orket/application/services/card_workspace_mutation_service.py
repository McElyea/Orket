"""Serialize supported workspace writes with final card evidence inspection."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from orket.core.contracts.repositories import CardRepository

MutationResult = TypeVar("MutationResult")


class CardWorkspaceMutationService:
    def __init__(self, cards: CardRepository):
        self.cards = cards

    async def run(self, operation: Callable[[], Awaitable[MutationResult]]) -> MutationResult:
        async def owned_write() -> MutationResult:
            async with self.cards.completion_write_guard():
                return await operation()

        task = asyncio.create_task(owned_write())
        joined = asyncio.gather(task, return_exceptions=True)
        cancelled = False
        while True:
            try:
                result, = await asyncio.shield(joined)
                break
            except asyncio.CancelledError:
                # Keep ownership until file I/O and transaction release have both finished.
                cancelled = True
        if cancelled:
            if isinstance(result, BaseException):
                logging.getLogger(__name__).warning("Card workspace write failed during cancellation drain: %r", result)
            raise asyncio.CancelledError
        if isinstance(result, BaseException):
            raise result
        return result
