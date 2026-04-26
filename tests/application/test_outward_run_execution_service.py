from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.adapters.storage.outward_approval_store import OutwardApprovalStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.adapters.tools.registry import DEFAULT_BUILTIN_CONNECTOR_REGISTRY
from orket.application.services.outward_approval_service import OutwardApprovalService
from orket.application.services.outward_model_tool_call_service import OutwardModelToolCallService
from orket.application.services.outward_run_execution_service import OutwardRunExecutionService
from orket.application.services.outward_run_service import OutwardRunService


class _Clock:
    def __init__(self, now: str) -> None:
        self._now = datetime.fromisoformat(now)
        if self._now.tzinfo is None:
            self._now = self._now.replace(tzinfo=UTC)

    def __call__(self) -> str:
        value = self._now.isoformat()
        self._now += timedelta(seconds=1)
        return value

    def set(self, now: str) -> None:
        self._now = datetime.fromisoformat(now)
        if self._now.tzinfo is None:
            self._now = self._now.replace(tzinfo=UTC)


def _approval_service(db_path: Path, clock: _Clock) -> OutwardApprovalService:
    return OutwardApprovalService(
        approval_store=OutwardApprovalStore(db_path),
        run_store=OutwardRunStore(db_path),
        event_store=OutwardRunEventStore(db_path),
        connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
        utc_now=clock,
    )


class _FakeModelClient:
    def __init__(self, *, tool: str, args: dict[str, object]) -> None:
        self.tool = tool
        self.args = args
        self.messages: list[dict[str, str]] = []
        self.runtime_context: dict[str, object] = {}
        self.closed = False

    async def complete(self, messages, runtime_context=None):
        self.messages = list(messages)
        self.runtime_context = dict(runtime_context or {})
        return SimpleNamespace(
            content="",
            raw={
                "tool_calls": [{"type": "function", "function": {"name": self.tool, "arguments": self.args}}],
                "provider_name": "fake-provider",
                "provider_backend": "fake-provider",
                "model": "fake-model",
                "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
                "latency_ms": 23,
                "orket_session_id": "fake-session",
                "openai_compat": {"choices": [{"finish_reason": "tool_calls"}]},
            },
        )

    async def close(self) -> None:
        self.closed = True


class _SequenceModelClient:
    def __init__(self, calls: list[dict[str, object]]) -> None:
        self.calls = list(calls)
        self.index = 0
        self.messages_by_call: list[list[dict[str, str]]] = []
        self.runtime_contexts: list[dict[str, object]] = []
        self.closed_count = 0

    async def complete(self, messages, runtime_context=None):
        call = self.calls[self.index]
        self.index += 1
        self.messages_by_call.append(list(messages))
        self.runtime_contexts.append(dict(runtime_context or {}))
        return SimpleNamespace(
            content="",
            raw={
                "tool_calls": [{"type": "function", "function": {"name": call["tool"], "arguments": call["args"]}}],
                "provider_name": "fake-provider",
                "provider_backend": "fake-provider",
                "model": "fake-model",
                "usage": {"prompt_tokens": 11 + self.index, "completion_tokens": 7, "total_tokens": 18 + self.index},
                "latency_ms": 23,
                "orket_session_id": f"fake-session-{self.index}",
                "openai_compat": {"choices": [{"finish_reason": "tool_calls"}]},
            },
        )

    async def close(self) -> None:
        self.closed_count += 1


def _execution_service(
    db_path: Path,
    workspace_root: Path,
    clock: _Clock,
    *,
    model_client: _FakeModelClient | None = None,
    model_tool: str = "write_file",
    model_args: dict[str, object] | None = None,
) -> OutwardRunExecutionService:
    client = model_client or _FakeModelClient(
        tool=model_tool,
        args=model_args or {"path": "approved.txt", "content": "approved content"},
    )
    return OutwardRunExecutionService(
        run_store=OutwardRunStore(db_path),
        event_store=OutwardRunEventStore(db_path),
        approval_service=_approval_service(db_path, clock),
        connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
        workspace_root=workspace_root,
        utc_now=clock,
        model_tool_call_service=OutwardModelToolCallService(
            connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
            workspace_root=workspace_root,
            model_client_factory=lambda: client,
        ),
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_outward_execution_pauses_before_write_and_continues_after_approval(tmp_path) -> None:
    """Layer: integration. Verifies explicit outward write_file execution pauses before effect and resumes."""
    db_path = tmp_path / "phase2-execution.sqlite3"
    clock = _Clock("2026-04-25T12:00:00+00:00")
    run_service = OutwardRunService(
        run_store=OutwardRunStore(db_path),
        event_store=OutwardRunEventStore(db_path),
        run_id_factory=lambda: "generated",
        utc_now=clock,
    )
    target = tmp_path / "approved.txt"
    fake_model = _FakeModelClient(
        tool="write_file",
        args={"path": "approved.txt", "content": "model approved content"},
    )

    run = await run_service.submit(
        {
            "run_id": "run-exec",
            "task": {
                "description": "Write approved file",
                "instruction": "Call the governed write_file connector",
                "acceptance_contract": {
                    "governed_tool_call": {
                        "tool": "write_file",
                        "args": {"path": "approved.txt", "content": "contract content"},
                    }
                },
            },
            "policy_overrides": {"approval_required_tools": ["write_file"], "approval_timeout_seconds": 30},
        }
    )

    paused = await _execution_service(db_path, tmp_path, clock, model_client=fake_model).start_if_ready(run.run_id)

    assert paused.status == "approval_required"
    assert target.exists() is False
    assert fake_model.closed is True
    prompt_payload = json.loads(fake_model.messages[1]["content"])
    assert prompt_payload["task"]["description"] == "Write approved file"
    assert prompt_payload["task"]["instruction"] == "Call the governed write_file connector"
    assert "contract content" not in fake_model.messages[1]["content"]
    proposals = await OutwardApprovalStore(db_path).list(status="pending")
    assert len(proposals) == 1
    assert proposals[0].args_preview["content"] == "[REDACTED]"

    clock.set("2026-04-25T12:01:00+00:00")
    approved = await _approval_service(db_path, clock).approve(proposals[0].proposal_id, operator_ref="operator:test")
    completed = await _execution_service(db_path, tmp_path, clock).continue_after_approval(approved.proposal_id)

    assert completed.status == "completed"
    assert target.read_text(encoding="utf-8") == "model approved content"
    model_invocation = json.loads(
        (tmp_path / "workspace" / "issue_run-exec" / "runs" / "run-exec" / "model_invocation.json").read_text(
            encoding="utf-8"
        )
    )
    model_response = json.loads(
        (tmp_path / "workspace" / "issue_run-exec" / "runs" / "run-exec" / "model_response_redacted.json").read_text(
            encoding="utf-8"
        )
    )
    proposal_extraction = json.loads(
        (tmp_path / "workspace" / "issue_run-exec" / "runs" / "run-exec" / "proposal_extraction.json").read_text(
            encoding="utf-8"
        )
    )
    assert model_invocation["provider_name"] == "fake-provider"
    assert model_invocation["model_name"] == "fake-model"
    assert model_invocation["session_id"] == "fake-session"
    assert model_invocation["prompt_token_count"] == 11
    assert model_invocation["completion_token_count"] == 7
    assert model_invocation["duration_ms"] == 23
    assert model_invocation["finish_reason"] == "tool_calls"
    assert model_invocation["model_invocation_ref"] == "workspace/issue_run-exec/runs/run-exec/model_invocation_turn_1.json"
    assert model_invocation["model_response_content_sha256"]
    assert model_response["extracted_tool_call_redacted"]["tool"] == "write_file"
    assert model_response["extracted_tool_call_redacted"]["args"]["content"] == "[REDACTED]"
    assert proposal_extraction["proposal_id"] == "proposal:run-exec:write_file:0001"
    assert proposal_extraction["acceptance_result"] == "accepted_for_proposal"
    assert proposal_extraction["model_response_content_sha256"] == model_invocation["model_response_content_sha256"]
    events = await OutwardRunEventStore(db_path).list_for_run("run-exec")
    assert [event.event_type for event in events] == [
        "run_submitted",
        "run_started",
        "turn_started",
        "proposal_made",
        "proposal_pending_approval",
        "proposal_approved",
        "tool_invoked",
        "commitment_recorded",
        "turn_completed",
        "run_completed",
    ]
    tool_event = next(event for event in events if event.event_type == "tool_invoked")
    assert tool_event.payload["args_hash"]
    proposal_event = next(event for event in events if event.event_type == "proposal_made")
    assert proposal_event.payload["model_invocation_ref"] == "workspace/issue_run-exec/runs/run-exec/model_invocation_turn_1.json"
    assert proposal_event.payload["model_invocation_sha256"]
    assert proposal_event.payload["model_response_content_sha256"] == model_invocation["model_response_content_sha256"]
    assert proposal_event.payload["tool_name"] == "write_file"
    assert proposal_event.payload["tool_args_hash"] == proposal_extraction["extracted_args_hash"]
    assert "model approved content" not in str(tool_event.payload)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_outward_execution_denial_keeps_effect_absent(tmp_path) -> None:
    """Layer: integration. Verifies denial leaves the planned write_file effect absent and completes cleanly."""
    db_path = tmp_path / "phase2-denied-execution.sqlite3"
    clock = _Clock("2026-04-25T12:00:00+00:00")
    run_service = OutwardRunService(
        run_store=OutwardRunStore(db_path),
        event_store=OutwardRunEventStore(db_path),
        run_id_factory=lambda: "generated",
        utc_now=clock,
    )
    target = tmp_path / "denied.txt"
    run = await run_service.submit(
        {
            "run_id": "run-denied-exec",
            "task": {
                "description": "Write denied file",
                "instruction": "Call the governed write_file connector",
                "acceptance_contract": {
                    "governed_tool_call": {
                        "tool": "write_file",
                        "args": {"path": "denied.txt", "content": "denied content"},
                    }
                },
            },
            "policy_overrides": {"approval_required_tools": ["write_file"]},
        }
    )

    await _execution_service(
        db_path,
        tmp_path,
        clock,
        model_args={"path": "denied.txt", "content": "denied content"},
    ).start_if_ready(run.run_id)
    proposal = (await OutwardApprovalStore(db_path).list(status="pending"))[0]
    denied = await _approval_service(db_path, clock).deny(
        proposal.proposal_id,
        operator_ref="operator:test",
        reason="not allowed",
    )
    completed = await _execution_service(db_path, tmp_path, clock).continue_after_denial(denied.proposal_id)

    assert denied.status == "denied"
    assert target.exists() is False
    assert completed.status == "completed"
    assert completed.stop_reason == "not allowed"
    events = await OutwardRunEventStore(db_path).list_for_run("run-denied-exec")
    event_types = [event.event_type for event in events]
    assert "tool_invoked" not in event_types
    assert event_types.index("proposal_denied") < event_types.index("run_completed")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_outward_execution_two_step_read_then_write_tracks_turn_boundary(tmp_path) -> None:
    """Layer: integration. Verifies a two-step governed sequence creates two proposals across two turns."""
    db_path = tmp_path / "phase2-multi-step.sqlite3"
    clock = _Clock("2026-04-25T12:00:00+00:00")
    (tmp_path / "seed.txt").write_text("pear\nbanana\napple\n", encoding="utf-8")
    model = _SequenceModelClient(
        [
            {"tool": "read_file", "args": {"path": "seed.txt"}},
            {"tool": "write_file", "args": {"path": "sorted.txt", "content": "apple\nbanana\npear\n"}},
        ]
    )
    run_service = OutwardRunService(
        run_store=OutwardRunStore(db_path),
        event_store=OutwardRunEventStore(db_path),
        run_id_factory=lambda: "generated",
        utc_now=clock,
    )
    run = await run_service.submit(
        {
            "run_id": "run-two-step",
            "task": {
                "description": "Read the seed list and write it sorted.",
                "instruction": "First read seed.txt, then write sorted.txt with sorted lines.",
                "acceptance_contract": {
                    "governed_tool_sequence": [
                        {"tool": "read_file", "args": {"path": "seed.txt"}},
                        {"tool": "write_file", "args": {"path": "sorted.txt", "content": "contract probe"}},
                    ]
                },
            },
            "policy_overrides": {"approval_required_tools": ["read_file", "write_file"], "max_turns": 2},
        }
    )

    paused_1 = await _execution_service(db_path, tmp_path, clock, model_client=model).start_if_ready(run.run_id)
    proposal_1 = (await OutwardApprovalStore(db_path).list(status="pending"))[0]
    approved_1 = await _approval_service(db_path, clock).approve(proposal_1.proposal_id, operator_ref="operator:test")
    paused_2 = await _execution_service(db_path, tmp_path, clock, model_client=model).continue_after_approval(approved_1.proposal_id)
    proposal_2 = (await OutwardApprovalStore(db_path).list(status="pending"))[0]

    assert paused_1.status == "approval_required"
    assert paused_2.status == "approval_required"
    assert proposal_1.proposal_id != proposal_2.proposal_id
    assert proposal_1.tool == "read_file"
    assert proposal_2.tool == "write_file"
    assert (tmp_path / "sorted.txt").exists() is False
    assert "pear" in model.messages_by_call[1][1]["content"]

    approved_2 = await _approval_service(db_path, clock).approve(proposal_2.proposal_id, operator_ref="operator:test")
    completed = await _execution_service(db_path, tmp_path, clock, model_client=model).continue_after_approval(approved_2.proposal_id)

    assert completed.status == "completed"
    assert completed.current_turn == 2
    assert (tmp_path / "sorted.txt").read_text(encoding="utf-8") == "apple\nbanana\npear\n"
    events = await OutwardRunEventStore(db_path).list_for_run("run-two-step")
    assert [event.event_type for event in events].count("proposal_made") == 2
    assert [event.event_type for event in events].count("proposal_approved") == 2
    assert [event.turn for event in events if event.event_type == "proposal_made"] == [1, 2]
    assert (tmp_path / "workspace" / "issue_run-two-step" / "runs" / "run-two-step" / "model_invocation_turn_2.json").exists()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_outward_execution_policy_rejects_out_of_scope_model_path_before_approval(tmp_path) -> None:
    """Layer: integration. Verifies workspace containment rejects an out-of-scope model path before approval."""
    db_path = tmp_path / "phase2-policy-reject.sqlite3"
    clock = _Clock("2026-04-25T12:00:00+00:00")
    run_service = OutwardRunService(
        run_store=OutwardRunStore(db_path),
        event_store=OutwardRunEventStore(db_path),
        run_id_factory=lambda: "generated",
        utc_now=clock,
    )
    run = await run_service.submit(
        {
            "run_id": "run-policy-reject",
            "task": {
                "description": "Attempt an out-of-scope write",
                "instruction": "Call write_file outside the workspace.",
                "acceptance_contract": {
                    "governed_tool_call": {
                        "tool": "write_file",
                        "args": {"path": "contract.txt", "content": "contract probe"},
                    }
                },
            },
            "policy_overrides": {"approval_required_tools": ["write_file"]},
        }
    )

    outside_name = f"{tmp_path.name}-sensitive.txt"
    completed = await _execution_service(
        db_path,
        tmp_path,
        clock,
        model_args={"path": f"../{outside_name}", "content": "blocked"},
    ).start_if_ready(run.run_id)

    assert completed.status == "completed"
    assert (tmp_path.parent / outside_name).exists() is False
    assert await OutwardApprovalStore(db_path).list(status="pending") == []
    events = await OutwardRunEventStore(db_path).list_for_run("run-policy-reject")
    event_types = [event.event_type for event in events]
    assert "proposal_made" in event_types
    assert "proposal_policy_rejected" in event_types
    assert "proposal_pending_approval" not in event_types
    rejection = next(event for event in events if event.event_type == "proposal_policy_rejected")
    assert rejection.payload["args_preview"]["path"] == f"../{outside_name}"
    assert rejection.payload["policy_result"] == "rejected"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_outward_execution_delete_file_uses_hardened_connector_after_approval(tmp_path) -> None:
    """Layer: integration. Verifies Phase 5 delete_file execution is gated and recorded through connector service."""
    db_path = tmp_path / "phase5-delete-execution.sqlite3"
    clock = _Clock("2026-04-25T12:00:00+00:00")
    run_service = OutwardRunService(
        run_store=OutwardRunStore(db_path),
        event_store=OutwardRunEventStore(db_path),
        run_id_factory=lambda: "generated",
        utc_now=clock,
    )
    target = tmp_path / "delete-me.txt"
    target.write_text("delete me", encoding="utf-8")
    run = await run_service.submit(
        {
            "run_id": "run-delete-exec",
            "task": {
                "description": "Delete approved file",
                "instruction": "Call delete_file",
                "acceptance_contract": {
                    "governed_tool_call": {
                        "tool": "delete_file",
                        "args": {"path": "delete-me.txt"},
                    }
                },
            },
            "policy_overrides": {"approval_required_tools": ["delete_file"]},
        }
    )

    paused = await _execution_service(
        db_path,
        tmp_path,
        clock,
        model_tool="delete_file",
        model_args={"path": "delete-me.txt"},
    ).start_if_ready(run.run_id)
    assert paused.status == "approval_required"
    assert target.exists() is True

    proposal = (await OutwardApprovalStore(db_path).list(status="pending"))[0]
    approved = await _approval_service(db_path, clock).approve(proposal.proposal_id, operator_ref="operator:test")
    completed = await _execution_service(db_path, tmp_path, clock).continue_after_approval(approved.proposal_id)

    assert completed.status == "completed"
    assert target.exists() is False
    events = await OutwardRunEventStore(db_path).list_for_run("run-delete-exec")
    tool_event = next(event for event in events if event.event_type == "tool_invoked")
    assert set(tool_event.payload) == {"connector_name", "args_hash", "result_summary", "duration_ms", "outcome"}
    assert tool_event.payload["connector_name"] == "delete_file"
    assert tool_event.payload["outcome"] == "success"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_outward_execution_rejects_invalid_connector_args_before_proposal(tmp_path) -> None:
    """Layer: integration. Verifies invalid connector args fail before approval proposal or side effect."""
    db_path = tmp_path / "phase5-invalid-args.sqlite3"
    clock = _Clock("2026-04-25T12:00:00+00:00")
    run_service = OutwardRunService(
        run_store=OutwardRunStore(db_path),
        event_store=OutwardRunEventStore(db_path),
        run_id_factory=lambda: "generated",
        utc_now=clock,
    )
    run = await run_service.submit(
        {
            "run_id": "run-invalid-connector-args",
            "task": {
                "description": "Write missing content",
                "instruction": "Call write_file",
                "acceptance_contract": {
                    "governed_tool_call": {
                        "tool": "write_file",
                        "args": {"path": "missing-content.txt", "content": "contract content"},
                    }
                },
            },
            "policy_overrides": {"approval_required_tools": ["write_file"]},
        }
    )

    failed = await _execution_service(
        db_path,
        tmp_path,
        clock,
        model_args={"path": "missing-content.txt"},
    ).start_if_ready(run.run_id)

    assert failed.status == "failed"
    assert (tmp_path / "missing-content.txt").exists() is False
    assert await OutwardApprovalStore(db_path).list(status="pending") == []
    assert "invalid model connector args" in str(failed.stop_reason)
