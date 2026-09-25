"""Real file/SQLite setup and controlled file-worker holds for result ownership tests."""
from __future__ import annotations

import asyncio
import json
import threading
from contextlib import asynccontextmanager
from copy import deepcopy

from orket.application.services.turn_tool_control_plane_service import build_turn_tool_control_plane_service
from orket.application.workflows.turn_artifact_writer import TurnArtifactWriter
from orket.application.workflows.turn_tool_result_persistence import (
    persist_non_protocol_tool_result_if_needed,
    persist_protocol_operation,
)
from tests.helpers.turn_artifacts import artifact_destination


class ResultCase:
    def __init__(self, workspace, protocol, *, governed=True):
        self.protocol = protocol
        self.governed = governed
        self.writer = TurnArtifactWriter(workspace)
        self.service = build_turn_tool_control_plane_service(workspace / "control-plane.sqlite3")
        self.identity = dict(session_id="result-run", issue_id="ISSUE-1", role_name="developer", turn_index=1)
        self.destination = artifact_destination(self.writer, **self.identity)
        self.args = {"path": "agent_output/out.txt", "content": "captured", "nested": {"values": ["first"]}}
        self.result = {"ok": True, "touched_paths": [self.args["path"]], "nested": {"values": ["first"]}}
        self.binding = {"declared_namespace_scopes": ["issue:ISSUE-1"], "tool_contract_version": "1.0.0"}
        self.context = {"validator_duration_ms": 1.25}
        self.capsule = {"policy": {"values": ["first"]}}
        self.expected = deepcopy((self.args, self.result, self.binding, self.context, self.capsule))
        self.operation = self.writer.persist_operation_result
        self.secondary = self.writer.append_protocol_receipt if protocol else self.writer.persist_tool_result
        self.directory = workspace / "observability/result-run/issue-1/001_developer"

    async def admit(self):
        await asyncio.to_thread(self.directory.mkdir, parents=True)
        if not self.governed:
            return
        self.run, self.attempt = await self.service.begin_execution(**self.identity, proposal_hash="proposal-1")
        await self.service.prepare_dispatch(run_id=self.run.run_id, attempt_id=self.attempt.attempt_id,
            step_id="operation-1", operation_id="operation-1", tool_name="write_file",
            tool_args=self.args, binding=self.binding)

    async def persist(self):
        common = dict(destination=self.destination, tool_name="write_file", tool_args=self.args, result=self.result,
            binding=self.binding, operation_id="operation-1", replayed=False, operation_record_present=False,
            persist_operation_result=self.operation, control_plane_enabled=self.governed,
            control_plane_service=self.service if self.governed else None,
            control_plane_run_id=self.run.run_id if self.governed else None,
            control_plane_attempt_id=self.attempt.attempt_id if self.governed else None)
        if self.protocol:
            return await persist_protocol_operation(**common, index=0, step_id="step-1", receipt_seq=1,
                proposal_hash="proposal-1", validator_version="validator-v1", protocol_hash="protocol-hash",
                tool_schema_hash="tool-schema", execution_capsule=self.capsule, context=self.context,
                append_protocol_receipt=self.secondary, retry_count=0)
        return await persist_non_protocol_tool_result_if_needed(**common, persist_tool_result=self.secondary)

    async def records(self):
        steps = await self.service.execution_repository.list_step_records(attempt_id=self.attempt.attempt_id)
        effects = await self.service.publication.repository.list_effect_journal_entries(run_id=self.run.run_id)
        return steps, effects

    async def artifacts(self):
        def read():
            operation = json.loads((self.directory / "operations/operation-1.json").read_text(encoding="utf-8"))
            if self.protocol:
                rows = (self.directory / "protocol_receipts.log").read_text(encoding="utf-8").splitlines()
                return operation, json.loads(rows[0])
            path = self.writer.tool_result_path(destination=self.destination, tool_name="write_file", tool_args=self.expected[0])
            return operation, json.loads(path.read_text(encoding="utf-8"))
        return await asyncio.to_thread(read)

    def mutate(self):
        self.args["nested"]["values"].append("MUTATED")
        self.result["nested"]["values"].append("MUTATED")
        self.binding["declared_namespace_scopes"].append("issue:MUTATED")
        self.context["validator_duration_ms"] = 99.0
        self.capsule["policy"]["values"].append("MUTATED")


@asynccontextmanager
async def held_worker(case, stage, *, fail=False):
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = getattr(case, stage)

    def held(**kwargs):
        entered.set()
        try:
            assert release.wait(10), "file worker was not released"
            result = original(**kwargs)
            if fail:
                raise OSError("controlled result-file failure")
            return result
        finally:
            finished.set()

    setattr(case, stage, held)
    try:
        yield entered, release, finished
    finally:
        release.set()
        if entered.is_set():
            assert await asyncio.to_thread(finished.wait, 10)


async def enter(entered):
    assert await asyncio.to_thread(entered.wait, 10), "result worker did not start"
