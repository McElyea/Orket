"""Real completion receipts guard turn publication and artifact-backed reentry."""
from __future__ import annotations

import asyncio
import json
import sqlite3

import pytest

from orket.application.services.card_completion_turn_service import prepare_card_completion_turn
from orket.application.services.tool_gate_service import ToolGate
from orket.application.services.turn_tool_control_plane_service import build_turn_tool_control_plane_service
from orket.application.workflows.turn_executor import TurnExecutor
from orket.application.workflows.turn_message_builder import MessageBuilder
from orket.core.domain.records import IssueRecord
from orket.core.domain.state_machine import StateMachine
from orket.schema import CardStatus, IssueConfig, RoleConfig
from orket.tools import ToolBox
from tests.helpers.card_completion import completion_components, completion_definition, write_completion_source
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("deterministic_turn_clock")]


class CompletionModel:
    def __init__(self):
        self.calls = 0

    async def complete(self, messages):
        self.calls += 1
        return {"content": json.dumps({"content": "", "tool_calls": [
            {"tool": "update_issue_status", "args": {"status": "done"}},
        ]}), "raw": {"total_tokens": 1}}


class ObservedToolBox(ToolBox):
    calls = 0
    reopen_after_write = False

    async def execute(self, tool_name, args, context=None):
        self.calls += 1
        result = await super().execute(tool_name, args, context)
        if self.reopen_after_write and tool_name == "update_issue_status" and result.get("ok"):
            await self.cards.cards.update_status("card", CardStatus.CODE_REVIEW)
        return result


async def _runtime(tmp_path, protocol):
    workspace = tmp_path / "workspace"
    repo, service = completion_components(tmp_path / "cards.db", workspace)
    await write_completion_source(workspace)
    record = IssueRecord(id="card", summary="Increment", seat="integrity_guard", status=CardStatus.CODE_REVIEW,
                         params={"completion_acceptance": completion_definition().model_dump(mode="json")})
    await repo.save(record)
    context = {"session_id": "session", "issue_id": "card", "turn_index": 1, "current_status": "code_review",
               "role": "integrity_guard", "roles": ["integrity_guard"], "protocol_governed_enabled": protocol}
    await prepare_card_completion_turn(service=service, cards=repo, context=context, card_id="card",
                                       session_id="session", seat_name="integrity_guard", turn_index=1)
    gate = ToolGate(organization=None, workspace_root=workspace)
    toolbox = ObservedToolBox(None, str(workspace), [], db_path=repo.db_path, cards_repo=repo,
                              tool_gate=gate, card_completion=service)
    control_plane = build_turn_tool_control_plane_service(tmp_path / "control_plane.db")
    executor = TurnExecutor(StateMachine(), gate, workspace, control_plane_service=control_plane)
    role = RoleConfig(id="GUARD", summary="integrity_guard", description="Review", tools=["update_issue_status"])
    return repo, service, toolbox, control_plane, executor, IssueConfig.model_validate(record.model_dump()), role, context


def _store_snapshot(paths):
    snapshots = []
    for path in paths:
        if not path.exists():
            snapshots.append(None)
            continue
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as connection:
            connection.execute("PRAGMA query_only=ON")
            snapshots.append(tuple(connection.iterdump()))
    return snapshots


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol", [True, False], ids=["protocol", "non_protocol"])
@pytest.mark.parametrize("change", ["none", "reopen", "new_attempt", "scope", "missing_evidence"])
# Layer: integration
async def test_completed_card_reentry_requires_retained_receipt_without_rerunning_tools(tmp_path, protocol, change):
    repo, service, toolbox, plane, executor, issue, role, context = await _runtime(tmp_path, protocol)
    model = CompletionModel()
    first = await executor.execute_turn(issue, role, model, toolbox, context)
    assert first.success, first.error or first.violations
    assert (await repo.get_by_id("card")).status == CardStatus.DONE
    truth = await plane.publication.repository.get_final_truth(run_id="turn-tool-run:session:card:integrity_guard:0001")
    assert truth is not None and truth.result_class.value == "success"
    if change in {"reopen", "new_attempt"}:
        await repo.update_status("card", CardStatus.CODE_REVIEW)
        if change == "new_attempt":
            await service.begin_attempt(repo, card_id="card", run_id="later-run", attempt_id="later-attempt")
    elif change == "scope":
        context["card_completion_context"] = context["card_completion_context"].model_copy(update={"run_id": "other"})
    elif change == "missing_evidence":
        await asyncio.to_thread(service.acceptance.evidence_store.db_path.unlink)
    paths = [tmp_path / "cards.db", service.acceptance.evidence_store.db_path, tmp_path / "control_plane.db"]
    before = await asyncio.to_thread(_store_snapshot, paths)
    second = await executor.execute_turn(issue, role, model, toolbox, context)
    assert model.calls == 1 and toolbox.calls == 1
    if change == "none":
        assert second.success and second.turn.note == "control_plane_completed_replay"
        assert second.turn.tool_calls[0].result["completion_ref"] == first.turn.tool_calls[0].result["completion_ref"]
    else:
        assert not second.success and "Completion rejected" in second.error
    assert await asyncio.to_thread(_store_snapshot, paths) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol", [True, False], ids=["protocol", "non_protocol"])
# Layer: integration
async def test_completion_reopened_before_turn_publication_cannot_publish_success(tmp_path, protocol):
    repo, _, toolbox, plane, executor, issue, role, context = await _runtime(tmp_path, protocol)
    toolbox.reopen_after_write = True
    result = await executor.execute_turn(issue, role, CompletionModel(), toolbox, context)
    assert not result.success
    assert any("E_CARD_COMPLETION_RESULT_UNVERIFIED" in violation for violation in result.violations)
    assert (await repo.get_by_id("card")).status == CardStatus.CODE_REVIEW
    truth = await plane.publication.repository.get_final_truth(run_id="turn-tool-run:session:card:integrity_guard:0001")
    assert truth is not None and truth.result_class.value != "success"


@pytest.mark.asyncio
@pytest.mark.parametrize("compact", [True, False])
@pytest.mark.parametrize("sections", [(), ("project",), ("patch",), ("project", "patch"), ("patch", "project")])
# Layer: integration
async def test_declared_acceptance_survives_final_prompt_rendering(tmp_path, compact, sections):
    repo, service, _, _, _, issue, role, context = await _runtime(tmp_path, True)
    prompt = await prepare_card_completion_turn(service=service, cards=repo, context=context, card_id="card",
                                               session_id="session", seat_name="integrity_guard", turn_index=1)
    context["compact_turn_packet_enabled"] = compact
    section_text = {"project": "PROJECT CONTEXT (PAST DECISIONS):\nPast decision A\n\nPast decision B",
                    "patch": "PATCH:\nPatch instruction A\n\nPatch instruction B"}
    prompt = "Base instructions\n\n" + "\n\n".join(section_text[name] for name in sections) + prompt
    messages = await MessageBuilder(service.workspace_root).prepare_messages(
        issue=issue, role=role, context=context, system_prompt=prompt,
    )
    rendered = "\n".join(message["content"] for message in messages)
    assert rendered.count('Declared card acceptance:') == 1
    for name in sections:
        assert rendered.count(section_text[name].split('\n', 1)[1]) == 1
    assert '"state": "acceptance_satisfied"' in rendered
    assert '"acceptance_ref": "increment.v1"' in rendered
    if compact:
        assert '- available tools: update_issue_status' in rendered
        assert '"tool":"<allowed tool name>","args":{...}' in rendered
        assert 'runtime verifier passed; blocked is not allowed' not in rendered
