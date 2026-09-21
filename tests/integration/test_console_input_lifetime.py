"""Real pipe EOF and line input cannot release an interrupted console owner early."""
import asyncio
import builtins
import os
import threading

import pytest

from orket.application.services.runtime_console_service import read_console_line

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("ending", ["eof", "line"])
@pytest.mark.parametrize("stop", ["normal", "cancel", "timeout"])
async def test_console_pipe_settles_before_return_and_preserves_interruption(monkeypatch, ending, stop):
    read_fd, write_fd = os.pipe()
    reader, writer = os.fdopen(read_fd), os.fdopen(write_fd, "w")
    entered, finished = threading.Event(), threading.Event()

    def input_line(_prompt):
        try:
            entered.set()
            value = reader.readline()
            if not value:
                raise EOFError
            return value.rstrip("\r\n")
        finally:
            finished.set()

    monkeypatch.setattr(builtins, "input", input_line)

    async def invoke():
        async with asyncio.timeout(.05 if stop == "timeout" else 5):
            return await read_console_line("Driver> ")

    task = asyncio.create_task(invoke())
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        if stop == "cancel":
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        await asyncio.sleep(.08)
        assert not task.done() and not finished.is_set()
        if ending == "line":
            await asyncio.to_thread(writer.write, "hello\n")
        await asyncio.to_thread(writer.close)
        if stop == "normal":
            assert await asyncio.wait_for(task, 5) == ("hello" if ending == "line" else None)
        else:
            with pytest.raises(TimeoutError if stop == "timeout" else asyncio.CancelledError):
                await asyncio.wait_for(task, 5)
    finally:
        await asyncio.to_thread(writer.close)
        await asyncio.gather(task, return_exceptions=True)
        await asyncio.to_thread(reader.close)
    assert finished.is_set() and reader.closed and writer.closed
