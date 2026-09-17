"""Controlled UTC inputs that keep real elapsed time for native deadline proof."""
import asyncio
import runpy
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest


class ElapsedAgentClock:
    def __init__(self, epoch=None, started=None):
        self._epoch = epoch if epoch is not None else datetime(2026, 9, 14, tzinfo=UTC)
        self._started = started if started is not None else time.monotonic_ns()
        self._offset = timedelta()

    @property
    def elapsed_seconds(self):
        return (time.monotonic_ns() - self._started) / 1_000_000_000

    def now(self):
        return self._epoch + timedelta(seconds=self.elapsed_seconds) + self._offset

    def jump(self, seconds):
        self._offset += timedelta(seconds=seconds)


def _datetime_type(clock):
    class FixtureDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            observed = clock.now()
            return observed.astimezone(tz) if tz else observed.replace(tzinfo=None)

    return FixtureDateTime


@pytest.fixture
def elapsed_agent_clock(monkeypatch, request):
    """Only selected fixtures use these inputs; native waits and processes stay real."""
    from orket.extensions import governed_agent_invoker
    from tests.integration import test_governed_agent_acceptance_failures
    from tests.runtime import governed_agent_test_support

    clock = ElapsedAgentClock()
    fixture_datetime = _datetime_type(clock)
    for module in (governed_agent_invoker, governed_agent_test_support,
                   test_governed_agent_acceptance_failures, request.node.module):
        if getattr(module, "datetime", None) is datetime:
            monkeypatch.setattr(module, "datetime", fixture_datetime)
    original = asyncio.create_subprocess_exec
    bootstrap = str(Path(__file__).resolve())

    async def create(*args, **kwargs):
        if args[:3] == (sys.executable, "-m", "orket.extensions.agent_workload_subprocess"):
            # The child broker reads UTC too. Bootstrap its same clock input before
            # running the canonical module; preserve executable, arguments and pipes.
            args = (args[0], bootstrap, clock._epoch.isoformat(),
                    str(clock._started), *args[2:])
        return await original(*args, **kwargs)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
    return clock


def _run_child():
    from orket_extension_sdk import agent_broker

    clock = ElapsedAgentClock(datetime.fromisoformat(sys.argv[1]), int(sys.argv[2]))
    agent_broker.datetime = _datetime_type(clock)
    module = sys.argv[3]
    sys.argv = sys.argv[3:]
    runpy.run_module(module, run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    _run_child()
