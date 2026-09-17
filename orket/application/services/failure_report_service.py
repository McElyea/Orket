"""Publish failure artifacts while retaining their I/O through cancellation."""

from __future__ import annotations

import asyncio
from functools import partial
from pathlib import Path

import aiofiles

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread
from orket.core.domain.failure_reporter import PolicyViolationReport
from orket.core.domain.verification import AGENT_OUTPUT_DIR
from orket.logging import log_event


class FailureReportService:
    def __init__(self, workspace: Path) -> None:
        self.workspace = Path(workspace)

    async def publish(self, report: PolicyViolationReport) -> Path:
        """A saved event follows a closed report file; cancellation drains publication."""
        if not report.card_id or any(c in report.card_id for c in '/\\\x00<>:"|?*'):
            raise ValueError("Failure report card_id must be a portable file-name component")
        content = report.model_dump_json(indent=4)
        return await run_owned_io(
            lambda: self._publish(report, content), label="failure-report-publication", preserve_failure=True
        )

    async def _publish(self, report: PolicyViolationReport, content: str) -> Path:
        root = await run_owned_thread(self.workspace.resolve, label="failure-report-root")
        directory = await run_owned_thread((root / AGENT_OUTPUT_DIR).resolve, label="failure-report-directory")
        if not directory.is_relative_to(root):
            raise ValueError("Failure report directory is outside the workspace")
        await asyncio.to_thread(directory.mkdir, parents=True, exist_ok=True)
        path = directory / f"policy_violation_{report.card_id}.json"
        resolved = await run_owned_thread(path.resolve, label="failure-report-path")
        if not resolved.is_relative_to(directory):
            raise ValueError("Failure report path is outside the report directory")
        async with aiofiles.open(resolved, "w", encoding="utf-8") as stream:
            await stream.write(content)
        await run_owned_thread(
            partial(
                log_event,
                "policy_violation_report_saved",
                {"session_id": report.session_id, "card_id": report.card_id, "path": str(resolved)},
                root,
            ),
            label="failure-report-saved-event",
        )
        return resolved
