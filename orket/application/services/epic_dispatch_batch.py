"""Drain dispatched turns before retaining an epic pause or terminal outcome."""
import asyncio

from orket.exceptions import ApprovalPending, CardNotFound, ExecutionFailed


async def run_epic_dispatch_batch(candidates, dispatch):
    results = await asyncio.gather(*(dispatch(card) for card in candidates), return_exceptions=True)
    failures = [result for result in results if isinstance(result, BaseException)]
    if failures:
        # A terminal business failure must not hide another card's cancellation
        # or unconfirmed infrastructure effects after the whole batch is drained.
        cancelled = [failure for failure in failures if isinstance(failure, asyncio.CancelledError)]
        unresolved = [failure for failure in failures if not isinstance(failure, (ExecutionFailed, CardNotFound))]
        terminal = [failure for failure in failures if not isinstance(failure, ApprovalPending)]
        raise (cancelled or unresolved or terminal or failures)[0]
