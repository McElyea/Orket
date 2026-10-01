"""Application ownership of quickstart ledger, operator and file effects."""
from __future__ import annotations

import json
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any, TypeVar

import aiofiles

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread
from orket.adapters.storage.async_file_tools import capture_file_roots

Result = TypeVar("Result")


class QuickstartLedgerIO:
    def __init__(self, path: Path) -> None:
        self.path, = capture_file_roots([path])

    async def create(self, on_created: Callable[[], Result]) -> Result:
        path = self.path

        async def create_owned() -> Result:
            await run_owned_thread(partial(path.parent.mkdir, parents=True, exist_ok=True),
                                   label="quickstart-ledger-directory")
            async with aiofiles.open(path, "w", encoding="utf-8") as ledger_file:
                await ledger_file.write("")
            return on_created()

        return await run_owned_io(create_owned, label="quickstart-ledger-create", preserve_failure=True)

    async def append(self, line: str, on_published: Callable[[], Result]) -> Result:
        path = self.path

        async def publish() -> Result:
            async with aiofiles.open(path, "a", encoding="utf-8") as ledger_file:
                await ledger_file.write(line)
            return on_published()

        return await run_owned_io(publish, label="quickstart-ledger-emit", preserve_failure=True)

    async def load(self) -> list[dict[str, Any]]:
        path = self.path

        async def read_owned() -> list[dict[str, Any]]:
            events: list[dict[str, Any]] = []
            async with aiofiles.open(path, encoding="utf-8") as ledger_file:
                line_number = 0
                async for raw_line in ledger_file:
                    line_number += 1
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"ledger line {line_number} is not valid JSON: {exc.msg}") from exc
                    if not isinstance(payload, dict):
                        raise ValueError(f"ledger line {line_number} must be a JSON object")
                    events.append(payload)
            return events

        return await run_owned_io(read_owned, label="quickstart-ledger-read", preserve_failure=True)


class QuickstartActionIO:
    def __init__(self, workspace: Path) -> None:
        self.workspace, = capture_file_roots([workspace])

    @staticmethod
    async def request_decision(write_request: Callable[[], None], read_input: Callable[[str], str]) -> str:
        await run_owned_thread(write_request, label="quickstart-request-output")
        return await run_owned_thread(partial(read_input, "Approve this action? [a]pprove / [d]eny: "),
                                      label="quickstart-operator-input")

    @staticmethod
    async def write_file(path: Path, content: str) -> None:
        path, = capture_file_roots([path])
        await run_owned_thread(partial(path.parent.mkdir, parents=True, exist_ok=True),
                               label="quickstart-output-directory")
        await run_owned_thread(partial(path.write_text, content, encoding="utf-8"), label="quickstart-output-write")

    @staticmethod
    async def verify_file(path: Path, expected_content: str) -> None:
        path, = capture_file_roots([path])
        observed = await run_owned_thread(partial(path.read_text, encoding="utf-8"),
                                         label="quickstart-output-verification")
        if observed != expected_content:
            raise RuntimeError(f"file write verification failed for {path.as_posix()}")

    @staticmethod
    async def publish_result(write_result: Callable[[], None]) -> None:
        await run_owned_thread(write_result, label="quickstart-result-output")
