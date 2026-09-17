"""Application ownership from admitted child launch through confirmed native teardown."""
from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field

from orket.adapters.execution.owned_io import run_owned_io
from orket.adapters.execution.process_lifecycle import (
    await_process_stopped,
    drain_diagnostic_tail,
    terminate_process_tree,
)
from orket.core.contracts.governed_agent_ports import GovernedAgentInvocationBinding
from orket_extension_sdk import AgentFrameSequenceValidator


@dataclass(slots=True)
class AgentInvocationOwner:
    binding: GovernedAgentInvocationBinding
    process: asyncio.subprocess.Process | None = None
    parent_sequence: int = 2
    cancelled: bool = False
    cancel_sent: bool = False
    bootstrap_sent: bool = False
    write_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    close_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    finished: asyncio.Event = field(default_factory=asyncio.Event)
    parent_frames: AgentFrameSequenceValidator | None = None
    diagnostic_task: asyncio.Task | None = None
    diagnostic_tail: str = ""

    async def launch(self, launcher):
        async def capture():
            self.process = await launcher()
            self.diagnostic_task = asyncio.create_task(
                drain_diagnostic_tail(self.process.stderr), name="orket-agent-stderr")
            if self.process.stdin is None or self.process.stdout is None or self.process.stderr is None:
                raise OSError("E_AGENT_CHILD_PIPES_UNAVAILABLE")
        # Cancellation cannot erase a successful launch before its handle is captured.
        await run_owned_io(capture, label="governed-agent-launch", preserve_failure=True)

    async def stop(self, grace_period_seconds):
        if self.process is None:
            try:
                await asyncio.wait_for(self.finished.wait(), timeout=max(0.001, grace_period_seconds))
                return True
            except TimeoutError:
                return False  # A pending launch is not evidence that no child exists.
        async with self.close_lock:
            if not await await_process_stopped(self.process, timeout_seconds=grace_period_seconds):
                await terminate_process_tree(self.process)
            return self.process.returncode is not None

    async def close(self):
        async with self.close_lock:
            if self.process is not None:
                await terminate_process_tree(self.process)
                if self.process.stdin is not None:
                    self.process.stdin.close()
                    with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                        await self.process.stdin.wait_closed()
            if self.diagnostic_task is not None:
                tail, truncated = await self.diagnostic_task
                self.diagnostic_tail = ("<truncated>" if truncated else "") + tail.decode("utf-8", errors="replace")
        # Failed native termination or diagnostic settlement leaves ownership visible.
        self.finished.set()
