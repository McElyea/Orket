from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.application.middleware import MiddlewareOutcome, TurnLifecycleInterceptors
from orket.application.workflows.turn_executor import TurnExecutor
from orket.core.domain.state_machine import StateMachine
from orket.core.policies.tool_gate import ToolGate
from orket.schema import CardStatus, IssueConfig, RoleConfig


@pytest.mark.asyncio
async def test_turn_executor_emits_memory_trace_artifacts_when_visibility_mode_present(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    issue = IssueConfig(id="ISSUE-1", summary="Implement feature", status=CardStatus.READY)
    role = RoleConfig(id="DEV", summary="developer", description="Builds code", tools=["update_issue_status"])

    class _ModelClient:
        async def complete(self, _messages):
            return SimpleNamespace(
                content='{"tool":"update_issue_status","args":{"issue_id":"ISSUE-1","status":"done"}}',
                raw={"total_tokens": 7},
            )

    class _Toolbox:
        async def execute(self, _tool_name, _args, context=None):
            return {"ok": True}

    context = {
        "session_id": "sess-memory",
        "turn_index": 0,
        "issue_id": "ISSUE-1",
        "role": "developer",
        "roles": ["developer"],
        "current_status": "ready",
        "selected_model": "dummy-model",
        "required_action_tools": [],
        "required_statuses": [],
        "required_read_paths": [],
        "required_write_paths": [],
        "history": [],
        "visibility_mode": "read_only",
        "memory_snapshot_id": "snapshot-1",
        "model_config_id": "modelcfg-1",
        "policy_set_id": "policyset-1",
        "memory_retrieval_trace_events": [
            {
                "retrieval_event_id": "ret-1",
                "run_id": "sess-memory",
                "event_id": "evt-1",
                "policy_id": "p",
                "policy_version": "v1",
                "query_normalization_version": "json-v1",
                "query_fingerprint": "abc",
                "retrieval_mode": "text_to_vector",
                "candidate_count": 0,
                "selected_records": [],
                "applied_filters": {},
                "retrieval_trace_schema_version": "memory.retrieval_trace.v1",
            }
        ],
    }

    result = await executor.execute_turn(
        issue=issue,
        role=role,
        model_client=_ModelClient(),
        toolbox=_Toolbox(),
        context=context,
        system_prompt="SYSTEM",
    )
    assert result.success is True

    out_dir = Path(tmp_path) / "observability" / "sess-memory" / "ISSUE-1" / "000_developer"
    trace = json.loads((out_dir / "memory_trace.json").read_text(encoding="utf-8"))
    retrieval = json.loads((out_dir / "memory_retrieval_trace.json").read_text(encoding="utf-8"))

    assert trace["determinism_trace_schema_version"] == "memory.determinism_trace.v1"
    assert trace["visibility_mode"] == "read_only"
    assert trace["memory_snapshot_id"] == "snapshot-1"
    assert isinstance(trace["events"], list) and trace["events"]
    interceptors = [str(evt.get("interceptor")) for evt in trace["events"]]
    assert "before_prompt" in interceptors
    assert "after_model" in interceptors
    assert "before_tool" in interceptors
    assert "after_tool" in interceptors
    assert retrieval["retrieval_trace_schema_version"] == "memory.retrieval_trace.v1"
    assert len(retrieval["events"]) == 1


@pytest.mark.asyncio
async def test_turn_executor_emits_memory_trace_artifacts_for_before_prompt_short_circuit(tmp_path):
    class _ShortCircuitHooks:
        def before_prompt(self, _messages, **_kwargs):
            return MiddlewareOutcome(short_circuit=True, reason="blocked by test")

    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
        middleware=TurnLifecycleInterceptors([_ShortCircuitHooks()]),
    )
    issue = IssueConfig(id="ISSUE-1", summary="Implement feature", status=CardStatus.READY)
    role = RoleConfig(id="DEV", summary="developer", description="Builds code", tools=["update_issue_status"])

    class _ModelClient:
        async def complete(self, _messages):
            return SimpleNamespace(content="", raw={"total_tokens": 0})

    class _Toolbox:
        async def execute(self, _tool_name, _args, context=None):
            return {"ok": True}

    context = {
        "session_id": "sess-memory-fail",
        "turn_index": 0,
        "issue_id": "ISSUE-1",
        "role": "developer",
        "roles": ["developer"],
        "current_status": "ready",
        "selected_model": "dummy-model",
        "required_action_tools": [],
        "required_statuses": [],
        "required_read_paths": [],
        "required_write_paths": [],
        "history": [],
        "visibility_mode": "read_only",
        "memory_snapshot_id": "snapshot-1",
        "model_config_id": "modelcfg-1",
        "policy_set_id": "policyset-1",
    }

    result = await executor.execute_turn(
        issue=issue,
        role=role,
        model_client=_ModelClient(),
        toolbox=_Toolbox(),
        context=context,
        system_prompt="SYSTEM",
    )
    assert result.success is False

    out_dir = Path(tmp_path) / "observability" / "sess-memory-fail" / "ISSUE-1" / "000_developer"
    trace = json.loads((out_dir / "memory_trace.json").read_text(encoding="utf-8"))
    retrieval = json.loads((out_dir / "memory_retrieval_trace.json").read_text(encoding="utf-8"))

    assert trace["output"]["output_type"] == "error"
    assert any(str(evt.get("interceptor")) == "on_turn_failure" for evt in trace["events"])
    assert any(str(evt.get("decision_type")) == "before_prompt_short_circuit" for evt in trace["events"])
    assert retrieval["retrieval_trace_schema_version"] == "memory.retrieval_trace.v1"


@pytest.mark.asyncio
async def test_turn_executor_emits_memory_trace_artifacts_for_runtime_exception(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    issue = IssueConfig(id="ISSUE-1", summary="Implement feature", status=CardStatus.READY)
    role = RoleConfig(id="DEV", summary="developer", description="Builds code", tools=["update_issue_status"])

    class _FailingModelClient:
        async def complete(self, _messages):
            raise RuntimeError("boom")

    class _Toolbox:
        async def execute(self, _tool_name, _args, context=None):
            return {"ok": True}

    context = {
        "session_id": "sess-memory-exception",
        "turn_index": 0,
        "issue_id": "ISSUE-1",
        "role": "developer",
        "roles": ["developer"],
        "current_status": "ready",
        "selected_model": "dummy-model",
        "required_action_tools": [],
        "required_statuses": [],
        "required_read_paths": [],
        "required_write_paths": [],
        "history": [],
        "visibility_mode": "read_only",
        "memory_snapshot_id": "snapshot-1",
        "model_config_id": "modelcfg-1",
        "policy_set_id": "policyset-1",
    }

    result = await executor.execute_turn(
        issue=issue,
        role=role,
        model_client=_FailingModelClient(),
        toolbox=_Toolbox(),
        context=context,
        system_prompt="SYSTEM",
    )
    assert result.success is False

    out_dir = Path(tmp_path) / "observability" / "sess-memory-exception" / "ISSUE-1" / "000_developer"
    trace = json.loads((out_dir / "memory_trace.json").read_text(encoding="utf-8"))

    assert trace["output"]["output_type"] == "error"
    assert any(str(evt.get("interceptor")) == "on_turn_failure" for evt in trace["events"])
    assert any(str(evt.get("decision_type")) == "RuntimeError" for evt in trace["events"])
