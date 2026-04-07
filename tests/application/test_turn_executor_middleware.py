from __future__ import annotations

from pathlib import Path

import pytest

from orket.application.middleware import MiddlewareOutcome, TurnLifecycleInterceptors
from orket.application.services.turn_tool_control_plane_service import build_turn_tool_control_plane_service
from orket.application.workflows.turn_executor import TurnExecutor
from orket.core.domain import AttemptState, RunState
from orket.core.domain.state_machine import StateMachine
from orket.core.policies.tool_gate import ToolGate
from orket.exceptions import ModelConnectionError
from orket.schema import CardStatus, IssueConfig, RoleConfig


class _ToolBox:
    def __init__(self):
        self.calls = []

    async def execute(self, tool_name, args, context=None):
        self.calls.append((tool_name, args))
        return {"ok": True, "tool": tool_name}


class _Model:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0

    async def complete(self, _messages):
        self.calls += 1
        idx = min(self.calls - 1, len(self.outputs) - 1)
        return {"content": self.outputs[idx], "raw": {"total_tokens": 1}}


def _current_status_for_role(role: str) -> str:
    if str(role or "").strip().lower() == "integrity_guard":
        return "awaiting_guard_review"
    return "in_progress"


class _TurnContext(dict):
    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        if key == "role":
            super().__setitem__("current_status", _current_status_for_role(str(value)))
        elif key == "roles" and value:
            first_role = next(iter(value), None)
            if first_role:
                super().__setitem__("current_status", _current_status_for_role(str(first_role)))


def _context():
    return _TurnContext(
        {
        "session_id": "sess-1",
        "issue_id": "ISSUE-1",
        "role": "developer",
        "roles": ["developer"],
        "current_status": _current_status_for_role("developer"),
        "selected_model": "dummy",
        "turn_index": 1,
        "history": [],
        }
    )


def _issue(status: str | CardStatus = CardStatus.IN_PROGRESS):
    return IssueConfig(id="ISSUE-1", summary="Implement feature", seat="developer", status=status)


def _guard_issue():
    return _issue(status=CardStatus.AWAITING_GUARD_REVIEW)


def _role():
    return RoleConfig(id="DEV", summary="developer", description="Build code", tools=["write_file"])


@pytest.mark.asyncio
async def test_turn_executor_middleware_hook_order(tmp_path):
    hook_order = []

    class _Hooks:
        def before_prompt(self, messages, **_kwargs):
            hook_order.append("before_prompt")
            return MiddlewareOutcome(replacement=messages)

        def after_model(self, response, **_kwargs):
            hook_order.append("after_model")
            return MiddlewareOutcome(replacement=response)

        def before_tool(self, tool_name, args, **_kwargs):
            hook_order.append(f"before_tool:{tool_name}")
            return None

        def after_tool(self, tool_name, args, result, **_kwargs):
            hook_order.append(f"after_tool:{tool_name}")
            return MiddlewareOutcome(replacement=result)

    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
        middleware=TurnLifecycleInterceptors([_Hooks()]),
    )
    model = _Model(['{"tool": "write_file", "args": {"path": "out.txt", "content": "ok"}}'])
    toolbox = _ToolBox()

    result = await executor.execute_turn(_issue(), _role(), model, toolbox, _context())
    assert result.success is True
    assert hook_order == ["before_prompt", "after_model", "before_tool:write_file", "after_tool:write_file"]


@pytest.mark.asyncio
async def test_turn_executor_isolates_broken_before_prompt_interceptor(tmp_path):
    """Layer: integration. Verifies a broken interceptor does not abort the turn."""
    hook_order = []

    class _BrokenHooks:
        def before_prompt(self, messages, **_kwargs):
            raise RuntimeError("broken interceptor")

    class _HealthyHooks:
        def before_prompt(self, messages, **_kwargs):
            hook_order.append("healthy_before_prompt")
            return MiddlewareOutcome(replacement=messages)

        def after_model(self, response, **_kwargs):
            hook_order.append("healthy_after_model")
            return MiddlewareOutcome(replacement=response)

    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
        middleware=TurnLifecycleInterceptors([_BrokenHooks(), _HealthyHooks()]),
    )
    model = _Model(['{"tool": "write_file", "args": {"path": "out.txt", "content": "ok"}}'])
    toolbox = _ToolBox()

    result = await executor.execute_turn(_issue(), _role(), model, toolbox, _context())

    assert result.success is True
    assert hook_order == ["healthy_before_prompt", "healthy_after_model"]
    assert toolbox.calls == [("write_file", {"path": "out.txt", "content": "ok"})]


@pytest.mark.asyncio
async def test_turn_executor_middleware_short_circuit_before_tool(tmp_path):
    class _Hooks:
        def before_tool(self, tool_name, args, **_kwargs):
            return MiddlewareOutcome(short_circuit=True, reason="blocked by middleware")

    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
        middleware=TurnLifecycleInterceptors([_Hooks()]),
    )
    model = _Model(['{"tool": "write_file", "args": {"path": "out.txt", "content": "ok"}}'])
    toolbox = _ToolBox()

    result = await executor.execute_turn(_issue(), _role(), model, toolbox, _context())
    assert result.success is False
    assert "blocked by middleware" in (result.error or "")


@pytest.mark.asyncio
async def test_turn_executor_calls_on_turn_failure_hook(tmp_path):
    hit = {"called": False}

    class _Hooks:
        def on_turn_failure(self, error, **_kwargs):
            hit["called"] = True

    class _FailingModel:
        async def complete(self, _messages):
            raise RuntimeError("boom")

    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
        middleware=TurnLifecycleInterceptors([_Hooks()]),
    )
    toolbox = _ToolBox()

    result = await executor.execute_turn(_issue(), _role(), _FailingModel(), toolbox, _context())
    assert result.success is False
    assert hit["called"] is True


@pytest.mark.asyncio
async def test_turn_executor_on_turn_failure_continues_after_broken_hook(tmp_path):
    """Layer: integration. Verifies failure hooks remain isolated from one another."""
    hit = {"called": False}

    class _BrokenHooks:
        def on_turn_failure(self, error, **_kwargs):
            raise RuntimeError("broken failure hook")

    class _HealthyHooks:
        def on_turn_failure(self, error, **_kwargs):
            hit["called"] = True

    class _FailingModel:
        async def complete(self, _messages):
            raise RuntimeError("boom")

    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
        middleware=TurnLifecycleInterceptors([_BrokenHooks(), _HealthyHooks()]),
    )

    result = await executor.execute_turn(_issue(), _role(), _FailingModel(), _ToolBox(), _context())

    assert result.success is False
    assert hit["called"] is True


@pytest.mark.asyncio
async def test_turn_executor_non_progress_fails_after_one_reprompt(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(["No-op", "Still no-op"])
    toolbox = _ToolBox()

    result = await executor.execute_turn(_issue(), _role(), model, toolbox, _context())
    assert result.success is False
    assert model.calls == 2
    assert "Deterministic failure" in (result.error or "")


@pytest.mark.asyncio
async def test_turn_executor_non_progress_recovery_after_reprompt(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            "No-op",
            '{"tool": "write_file", "args": {"path": "out.txt", "content": "ok"}}',
        ]
    )
    toolbox = _ToolBox()

    result = await executor.execute_turn(_issue(), _role(), model, toolbox, _context())
    assert result.success is True
    assert model.calls == 2
    assert len(toolbox.calls) == 1


@pytest.mark.asyncio
async def test_turn_executor_retries_transient_model_failure(tmp_path):
    """Layer: integration. Verifies transient model provider errors are retried before parsing."""

    class _FlakyModel:
        def __init__(self):
            self.calls = 0

        async def complete(self, _messages):
            self.calls += 1
            if self.calls == 1:
                raise ModelConnectionError("temporary outage")
            return {
                "content": '{"tool": "write_file", "args": {"path": "out.txt", "content": "ok"}}',
                "raw": {"total_tokens": 1},
            }

    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _FlakyModel()
    toolbox = _ToolBox()
    context = _context()
    context["max_turn_retries"] = 1
    context["turn_retry_backoff_seconds"] = 0

    result = await executor.execute_turn(_issue(), _role(), model, toolbox, context)

    assert result.success is True
    assert model.calls == 2
    assert toolbox.calls == [("write_file", {"path": "out.txt", "content": "ok"})]


@pytest.mark.asyncio
async def test_turn_executor_blocks_after_model_retry_exhaustion(tmp_path):
    """Layer: integration. Verifies exhausted transient model errors return a blocked turn result."""

    class _FailingModel:
        def __init__(self):
            self.calls = 0

        async def complete(self, _messages):
            self.calls += 1
            raise ModelConnectionError("provider unavailable")

    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _FailingModel()
    context = _context()
    context["max_turn_retries"] = 1
    context["turn_retry_backoff_seconds"] = 0

    result = await executor.execute_turn(_issue(), _role(), model, _ToolBox(), context)

    assert result.success is False
    assert result.should_retry is False
    assert model.calls == 2
    assert context["turn_retry_exhausted"] is True


@pytest.mark.asyncio
async def test_turn_executor_context_only_tool_call_is_non_progress(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "get_issue_context", "args": {}}',
            '{"tool": "get_issue_context", "args": {}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="REQ",
        summary="requirements_analyst",
        description="Gather requirements",
        tools=["get_issue_context", "write_file", "update_issue_status"],
    )
    context = _context()
    context["role"] = "requirements_analyst"
    context["roles"] = ["requirements_analyst"]

    result = await executor.execute_turn(
        _issue(),
        role,
        model,
        toolbox,
        context,
    )
    assert result.success is False
    assert model.calls == 2
    assert "Deterministic failure" in (result.error or "")


@pytest.mark.asyncio
async def test_turn_executor_enforces_required_status_after_reprompt(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "write_file", "args": {"path": "out.txt", "content": "ok"}}\n{"tool": "update_issue_status", "args": {"status": "in_progress"}}',
            '{"tool": "write_file", "args": {"path": "out.txt", "content": "ok"}}\n{"tool": "update_issue_status", "args": {"status": "code_review"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="REQ",
        summary="requirements_analyst",
        description="Gather requirements",
        tools=["write_file", "update_issue_status"],
    )
    context = _context()
    context["role"] = "requirements_analyst"
    context["roles"] = ["requirements_analyst"]
    context["required_action_tools"] = ["write_file", "update_issue_status"]
    context["required_statuses"] = ["code_review"]

    result = await executor.execute_turn(
        _issue(),
        role,
        model,
        toolbox,
        context,
    )
    assert result.success is True
    assert model.calls == 2
    assert len(toolbox.calls) == 2
    assert toolbox.calls[1][1]["status"] == "code_review"


@pytest.mark.asyncio
async def test_turn_executor_blocked_requires_wait_reason(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "update_issue_status", "args": {"status": "blocked"}}',
            '{"tool": "update_issue_status", "args": {"status": "blocked"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="GRD",
        summary="integrity_guard",
        description="Final gate",
        tools=["update_issue_status"],
    )
    context = _context()
    context["role"] = "integrity_guard"
    context["roles"] = ["integrity_guard"]
    context["required_action_tools"] = ["update_issue_status"]
    context["required_statuses"] = ["done", "blocked"]

    result = await executor.execute_turn(
        _issue(status=CardStatus.AWAITING_GUARD_REVIEW),
        role,
        model,
        toolbox,
        context,
    )
    assert result.success is False
    assert model.calls == 2
    assert len(toolbox.calls) == 0
    assert "Deterministic failure" in (result.error or "")


@pytest.mark.asyncio
async def test_turn_executor_blocks_approval_required_tool_and_persists_request(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(['{"tool": "write_file", "args": {"path": "out.txt", "content": "ok"}}'])
    toolbox = _ToolBox()

    request_calls = []

    async def _request_writer(*, tool_name, tool_args):
        request_calls.append({"tool_name": tool_name, "tool_args": tool_args})
        return "REQ-TOOL-1"

    context = _context()
    context["approval_required_tools"] = ["write_file"]
    context["create_pending_gate_request"] = _request_writer
    context["stage_gate_mode"] = "approval_required"

    result = await executor.execute_turn(_issue(), _role(), model, toolbox, context)

    assert result.success is False
    assert result.should_retry is True
    assert "Approval required for tool 'write_file'" in (result.error or "")
    assert len(toolbox.calls) == 0
    assert len(request_calls) == 1
    assert request_calls[0]["tool_name"] == "write_file"


@pytest.mark.asyncio
async def test_turn_executor_write_file_approval_resume_continues_same_governed_run(tmp_path):
    control_plane = build_turn_tool_control_plane_service(tmp_path / "control_plane.sqlite3")
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
        control_plane_service=control_plane,
    )
    model = _Model(['{"tool": "write_file", "args": {"path": "out.txt", "content": "ok"}}'])
    toolbox = _ToolBox()

    class _PendingRepo:
        def __init__(self) -> None:
            self.rows: list[dict[str, object]] = []

        async def create_request(self, **kwargs):
            request_id = f"REQ-{len(self.rows) + 1}"
            self.rows.append(
                {
                    "request_id": request_id,
                    "session_id": kwargs["session_id"],
                    "issue_id": kwargs["issue_id"],
                    "seat_name": kwargs["seat_name"],
                    "gate_mode": kwargs["gate_mode"],
                    "request_type": kwargs["request_type"],
                    "reason": kwargs["reason"],
                    "payload_json": dict(kwargs.get("payload") or {}),
                    "status": "pending",
                    "resolution_json": {},
                }
            )
            return request_id

        async def list_requests(self, *, session_id=None, status=None, limit=100):
            rows = list(self.rows)
            if session_id:
                rows = [row for row in rows if row["session_id"] == session_id]
            if status:
                rows = [row for row in rows if row["status"] == status]
            return rows[: max(1, int(limit))]

        async def resolve_request(self, *, request_id: str, status: str, resolution=None) -> None:
            for row in self.rows:
                if row["request_id"] == request_id:
                    row["status"] = status
                    row["resolution_json"] = dict(resolution or {})
                    return
            raise RuntimeError("request not found")

    repo = _PendingRepo()

    async def _request_writer(*, tool_name, tool_args):
        return await repo.create_request(
            session_id="sess-1",
            issue_id="ISSUE-1",
            seat_name="developer",
            gate_mode="approval_required",
            request_type="tool_approval",
            reason=f"approval_required_tool:{tool_name}",
            payload={
                "tool": tool_name,
                "args": dict(tool_args or {}),
                "role": "developer",
                "turn_index": 1,
                "control_plane_target_ref": "turn-tool-run:sess-1:ISSUE-1:developer:0001",
            },
        )

    async def _approved_lookup(*, tool_name, tool_args):
        rows = await repo.list_requests(session_id="sess-1", status="approved", limit=100)
        for row in rows:
            payload = row.get("payload_json")
            if not isinstance(payload, dict):
                continue
            if str(payload.get("tool") or "").strip() != tool_name:
                continue
            if dict(payload.get("args") or {}) != dict(tool_args or {}):
                continue
            return str(row["request_id"])
        return None

    first_context = _context()
    first_context["approval_required_tools"] = ["write_file"]
    first_context["create_pending_gate_request"] = _request_writer
    first_context["resolve_granted_tool_approval"] = _approved_lookup
    first_context["stage_gate_mode"] = "approval_required"
    first_context["run_namespace_scope"] = "issue:ISSUE-1"

    first = await executor.execute_turn(_issue(), _role(), model, toolbox, first_context)

    run_id = "turn-tool-run:sess-1:ISSUE-1:developer:0001"
    run = await control_plane.execution_repository.get_run_record(run_id=run_id)
    attempt = None if run is None else await control_plane.execution_repository.get_attempt_record(
        attempt_id=str(run.current_attempt_id or "")
    )
    truth = await control_plane.publication.repository.get_final_truth(run_id=run_id)

    assert first.success is False
    assert "Approval required for tool 'write_file'" in (first.error or "")
    assert model.calls == 1
    assert len(toolbox.calls) == 0
    assert len(repo.rows) == 1
    assert run is not None
    assert attempt is not None
    assert run.lifecycle_state is RunState.EXECUTING
    assert attempt.attempt_state is AttemptState.EXECUTING
    assert truth is None

    await repo.resolve_request(
        request_id=str(repo.rows[0]["request_id"]),
        status="approved",
        resolution={"decision": "approve"},
    )

    second_context = _context()
    second_context["approval_required_tools"] = ["write_file"]
    second_context["create_pending_gate_request"] = _request_writer
    second_context["resolve_granted_tool_approval"] = _approved_lookup
    second_context["stage_gate_mode"] = "approval_required"
    second_context["run_namespace_scope"] = "issue:ISSUE-1"
    second_context["resume_mode"] = True

    second = await executor.execute_turn(_issue(), _role(), model, toolbox, second_context)

    run = await control_plane.execution_repository.get_run_record(run_id=run_id)
    attempt = None if run is None else await control_plane.execution_repository.get_attempt_record(
        attempt_id=str(run.current_attempt_id or "")
    )
    truth = await control_plane.publication.repository.get_final_truth(run_id=run_id)

    assert second.success is True
    assert model.calls == 1
    assert toolbox.calls == [("write_file", {"path": "out.txt", "content": "ok"})]
    assert len(repo.rows) == 1
    assert run is not None
    assert attempt is not None
    assert truth is not None
    assert run.lifecycle_state is RunState.COMPLETED
    assert attempt.attempt_state is AttemptState.COMPLETED
    assert truth.result_class.value == "success"


@pytest.mark.asyncio
async def test_turn_executor_create_issue_approval_resume_continues_same_governed_run(tmp_path):
    """Layer: unit."""
    control_plane = build_turn_tool_control_plane_service(tmp_path / "control_plane.sqlite3")
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
        control_plane_service=control_plane,
    )
    model = _Model(['{"tool": "create_issue", "args": {"seat": "reviewer", "summary": "Follow-up task"}}'])
    toolbox = _ToolBox()
    role = RoleConfig(
        id="DEV",
        summary="developer",
        description="Build code",
        tools=["create_issue"],
    )

    class _PendingRepo:
        def __init__(self) -> None:
            self.rows: list[dict[str, object]] = []

        async def create_request(self, **kwargs):
            request_id = f"REQ-{len(self.rows) + 1}"
            self.rows.append(
                {
                    "request_id": request_id,
                    "session_id": kwargs["session_id"],
                    "issue_id": kwargs["issue_id"],
                    "seat_name": kwargs["seat_name"],
                    "gate_mode": kwargs["gate_mode"],
                    "request_type": kwargs["request_type"],
                    "reason": kwargs["reason"],
                    "payload_json": dict(kwargs.get("payload") or {}),
                    "status": "pending",
                    "resolution_json": {},
                }
            )
            return request_id

        async def list_requests(self, *, session_id=None, status=None, limit=100):
            rows = list(self.rows)
            if session_id:
                rows = [row for row in rows if row["session_id"] == session_id]
            if status:
                rows = [row for row in rows if row["status"] == status]
            return rows[: max(1, int(limit))]

        async def resolve_request(self, *, request_id: str, status: str, resolution=None) -> None:
            for row in self.rows:
                if row["request_id"] == request_id:
                    row["status"] = status
                    row["resolution_json"] = dict(resolution or {})
                    return
            raise RuntimeError("request not found")

    repo = _PendingRepo()

    async def _request_writer(*, tool_name, tool_args):
        return await repo.create_request(
            session_id="sess-1",
            issue_id="ISSUE-1",
            seat_name="developer",
            gate_mode="approval_required",
            request_type="tool_approval",
            reason=f"approval_required_tool:{tool_name}",
            payload={
                "tool": tool_name,
                "args": dict(tool_args or {}),
                "role": "developer",
                "turn_index": 1,
                "control_plane_target_ref": "turn-tool-run:sess-1:ISSUE-1:developer:0001",
            },
        )

    async def _approved_lookup(*, tool_name, tool_args):
        rows = await repo.list_requests(session_id="sess-1", status="approved", limit=100)
        for row in rows:
            payload = row.get("payload_json")
            if not isinstance(payload, dict):
                continue
            if str(payload.get("tool") or "").strip() != tool_name:
                continue
            if dict(payload.get("args") or {}) != dict(tool_args or {}):
                continue
            return str(row["request_id"])
        return None

    first_context = _context()
    first_context["approval_required_tools"] = ["create_issue"]
    first_context["create_pending_gate_request"] = _request_writer
    first_context["resolve_granted_tool_approval"] = _approved_lookup
    first_context["stage_gate_mode"] = "approval_required"
    first_context["run_namespace_scope"] = "issue:ISSUE-1"

    first = await executor.execute_turn(_issue(), role, model, toolbox, first_context)

    run_id = "turn-tool-run:sess-1:ISSUE-1:developer:0001"
    run = await control_plane.execution_repository.get_run_record(run_id=run_id)
    attempt = None if run is None else await control_plane.execution_repository.get_attempt_record(
        attempt_id=str(run.current_attempt_id or "")
    )
    truth = await control_plane.publication.repository.get_final_truth(run_id=run_id)

    assert first.success is False
    assert "Approval required for tool 'create_issue'" in (first.error or "")
    assert model.calls == 1
    assert len(toolbox.calls) == 0
    assert len(repo.rows) == 1
    assert run is not None
    assert attempt is not None
    assert run.lifecycle_state is RunState.EXECUTING
    assert attempt.attempt_state is AttemptState.EXECUTING
    assert truth is None

    await repo.resolve_request(
        request_id=str(repo.rows[0]["request_id"]),
        status="approved",
        resolution={"decision": "approve"},
    )

    second_context = _context()
    second_context["approval_required_tools"] = ["create_issue"]
    second_context["create_pending_gate_request"] = _request_writer
    second_context["resolve_granted_tool_approval"] = _approved_lookup
    second_context["stage_gate_mode"] = "approval_required"
    second_context["run_namespace_scope"] = "issue:ISSUE-1"
    second_context["resume_mode"] = True

    second = await executor.execute_turn(_issue(), role, model, toolbox, second_context)

    run = await control_plane.execution_repository.get_run_record(run_id=run_id)
    attempt = None if run is None else await control_plane.execution_repository.get_attempt_record(
        attempt_id=str(run.current_attempt_id or "")
    )
    truth = await control_plane.publication.repository.get_final_truth(run_id=run_id)

    assert second.success is True
    assert model.calls == 1
    assert toolbox.calls == [("create_issue", {"seat": "reviewer", "summary": "Follow-up task"})]
    assert len(repo.rows) == 1
    assert run is not None
    assert attempt is not None
    assert truth is not None
    assert run.lifecycle_state is RunState.COMPLETED
    assert attempt.attempt_state is AttemptState.COMPLETED
    assert truth.result_class.value == "success"


@pytest.mark.asyncio
async def test_turn_executor_guard_rejection_payload_contract_recovers_after_reprompt(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "update_issue_status", "args": {"status": "blocked", "wait_reason": "dependency"}}',
            '{"tool": "update_issue_status", "args": {"status": "blocked", "wait_reason": "dependency"}}\n'
            '{"rationale": "Missing evidence", "violations": ["No tests"], "remediation_actions": ["Add tests"]}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="GRD",
        summary="integrity_guard",
        description="Final gate",
        tools=["update_issue_status"],
    )
    context = _context()
    context["role"] = "integrity_guard"
    context["roles"] = ["integrity_guard"]
    context["required_action_tools"] = ["update_issue_status"]
    context["required_statuses"] = ["done", "blocked"]
    context["stage_gate_mode"] = "review_required"

    result = await executor.execute_turn(
        _issue(status=CardStatus.AWAITING_GUARD_REVIEW),
        role,
        model,
        toolbox,
        context,
    )
    assert result.success is True
    assert model.calls == 2
    assert len(toolbox.calls) == 1
    assert toolbox.calls[0][1]["status"] == "blocked"


@pytest.mark.asyncio
async def test_turn_executor_guard_rejection_payload_contract_fails_after_reprompt(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "update_issue_status", "args": {"status": "blocked", "wait_reason": "dependency"}}',
            '{"tool": "update_issue_status", "args": {"status": "blocked", "wait_reason": "dependency"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="GRD",
        summary="integrity_guard",
        description="Final gate",
        tools=["update_issue_status"],
    )
    context = _context()
    context["role"] = "integrity_guard"
    context["roles"] = ["integrity_guard"]
    context["required_action_tools"] = ["update_issue_status"]
    context["required_statuses"] = ["done", "blocked"]
    context["stage_gate_mode"] = "review_required"

    result = await executor.execute_turn(
        _guard_issue(),
        role,
        model,
        toolbox,
        context,
    )
    assert result.success is False
    assert model.calls == 2
    assert len(toolbox.calls) == 0
    assert "guard rejection payload contract not met" in (result.error or "")


@pytest.mark.asyncio
async def test_turn_executor_guard_payload_reprompt_still_enforces_progress_contract(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "update_issue_status", "args": {"status": "blocked", "wait_reason": "dependency"}}',
            '{"tool": "add_issue_comment", "args": {"comment": "Need more detail"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="GRD",
        summary="integrity_guard",
        description="Final gate",
        tools=["update_issue_status"],
    )
    context = _context()
    context["role"] = "integrity_guard"
    context["roles"] = ["integrity_guard"]
    context["required_action_tools"] = ["update_issue_status"]
    context["required_statuses"] = ["done", "blocked"]
    context["stage_gate_mode"] = "review_required"

    result = await executor.execute_turn(
        _guard_issue(),
        role,
        model,
        toolbox,
        context,
    )
    assert result.success is False
    assert model.calls == 2
    assert len(toolbox.calls) == 0
    assert "progress contract not met after corrective reprompt" in (result.error or "")


@pytest.mark.asyncio
async def test_prepare_messages_includes_guard_rejection_contract(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    messages = await executor._prepare_messages(
        _issue(),
        _role(),
        {
            **_context(),
            "stage_gate_mode": "review_required",
            "required_action_tools": ["update_issue_status"],
            "required_statuses": ["done", "blocked"],
        },
        None,
    )
    joined = "\n".join(str(m.get("content", "")) for m in messages)
    assert "Guard Review Rules" in joined
    assert "remediation_actions" in joined


@pytest.mark.asyncio
async def test_turn_executor_guard_dependency_block_rejected_when_dependencies_resolved(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "update_issue_status", "args": {"status": "blocked", "wait_reason": "dependency"}}\n'
            '{"rationale": "Dependency unresolved", "violations": ["dep"], "remediation_actions": ["wait"]}',
            '{"tool": "update_issue_status", "args": {"status": "blocked", "wait_reason": "dependency"}}\n'
            '{"rationale": "Dependency unresolved", "violations": ["dep"], "remediation_actions": ["wait"]}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="GRD",
        summary="integrity_guard",
        description="Final gate",
        tools=["update_issue_status"],
    )
    context = _context()
    context["role"] = "integrity_guard"
    context["roles"] = ["integrity_guard"]
    context["required_action_tools"] = ["update_issue_status"]
    context["required_statuses"] = ["done", "blocked"]
    context["stage_gate_mode"] = "review_required"
    context["dependency_context"] = {
        "depends_on": ["ARC-1"],
        "dependency_count": 1,
        "dependency_statuses": {"ARC-1": "done"},
        "unresolved_dependencies": [],
    }

    result = await executor.execute_turn(
        _guard_issue(),
        role,
        model,
        toolbox,
        context,
    )
    assert result.success is False
    assert model.calls == 2
    assert len(toolbox.calls) == 0
    assert "guard rejection payload contract not met" in (result.error or "")


@pytest.mark.asyncio
async def test_prepare_messages_includes_read_path_contract(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    (Path(tmp_path) / "agent_output").mkdir(parents=True, exist_ok=True)
    (Path(tmp_path) / "agent_output" / "main.py").write_text("print('ok')\n", encoding="utf-8")
    messages = await executor._prepare_messages(
        _issue(),
        _role(),
        {
            **_context(),
            "required_action_tools": ["read_file", "update_issue_status"],
            "required_statuses": ["code_review"],
            "required_read_paths": ["agent_output/main.py"],
        },
        None,
    )
    joined = "\n".join(str(m.get("content", "")) for m in messages)
    assert "TURN PACKET:" in joined
    assert "- required read paths: agent_output/main.py" in joined
    assert "agent_output/main.py" in joined


@pytest.mark.asyncio
async def test_prepare_messages_includes_write_path_contract(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    messages = await executor._prepare_messages(
        _issue(),
        _role(),
        {
            **_context(),
            "required_action_tools": ["write_file", "update_issue_status"],
            "required_statuses": ["code_review"],
            "required_write_paths": ["agent_output/main.py"],
        },
        None,
    )
    joined = "\n".join(str(m.get("content", "")) for m in messages)
    assert "TURN PACKET:" in joined
    assert "- required write paths: agent_output/main.py" in joined
    assert "agent_output/main.py" in joined


@pytest.mark.asyncio
async def test_turn_executor_write_path_contract_recovers_after_reprompt(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "write_file", "args": {"path": "agent_output/not_main.py", "content": "print(1)"}}'
            '\n{"tool": "update_issue_status", "args": {"status": "code_review"}}',
            '{"tool": "write_file", "args": {"path": "agent_output/main.py", "content": "print(1)"}}'
            '\n{"tool": "update_issue_status", "args": {"status": "code_review"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="COD",
        summary="coder",
        description="Implement code",
        tools=["write_file", "update_issue_status"],
    )
    context = _context()
    context["role"] = "coder"
    context["roles"] = ["coder"]
    context["required_action_tools"] = ["write_file", "update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["required_write_paths"] = ["agent_output/main.py"]

    result = await executor.execute_turn(
        _issue(),
        role,
        model,
        toolbox,
        context,
    )
    assert result.success is True
    assert model.calls == 2
    assert toolbox.calls[0][1]["path"] == "agent_output/main.py"


@pytest.mark.asyncio
async def test_turn_executor_read_path_contract_recovers_after_reprompt(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    (Path(tmp_path) / "agent_output").mkdir(parents=True, exist_ok=True)
    (Path(tmp_path) / "agent_output" / "main.py").write_text("print('ok')\n", encoding="utf-8")
    model = _Model(
        [
            '{"tool": "read_file", "args": {"path": "/path/to/implementation/file"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
            '{"tool": "read_file", "args": {"path": "agent_output/main.py"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="REV",
        summary="code_reviewer",
        description="Review code",
        tools=["read_file", "update_issue_status"],
    )
    context = _context()
    context["role"] = "code_reviewer"
    context["roles"] = ["code_reviewer"]
    context["required_action_tools"] = ["read_file", "update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["required_read_paths"] = ["agent_output/main.py"]

    result = await executor.execute_turn(
        _issue(),
        role,
        model,
        toolbox,
        context,
    )
    assert result.success is True
    assert model.calls == 2
    assert len(toolbox.calls) == 2
    assert toolbox.calls[0][1]["path"] == "agent_output/main.py"


@pytest.mark.asyncio
async def test_turn_executor_missing_required_read_paths_are_preflighted(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "read_file", "args": {"path": "agent_output/requirements.txt"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="REV",
        summary="code_reviewer",
        description="Review code",
        tools=["read_file", "update_issue_status"],
    )
    context = _context()
    context["role"] = "code_reviewer"
    context["roles"] = ["code_reviewer"]
    context["required_action_tools"] = ["read_file", "update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["required_read_paths"] = ["agent_output/requirements.txt", "agent_output/main.py"]

    result = await executor.execute_turn(
        _issue(),
        role,
        model,
        toolbox,
        context,
    )
    assert result.success is True
    assert model.calls == 1
    assert len(toolbox.calls) == 2
    assert toolbox.calls[0][0] == "read_file"
    assert toolbox.calls[1][0] == "update_issue_status"


@pytest.mark.asyncio
async def test_turn_executor_hallucination_scope_contract_recovers_after_reprompt(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "read_file", "args": {"path": "agent_output/not_allowed.py"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
            '{"tool": "read_file", "args": {"path": "agent_output/main.py"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="REV",
        summary="code_reviewer",
        description="Review code",
        tools=["read_file", "update_issue_status"],
    )
    context = _context()
    context["role"] = "code_reviewer"
    context["roles"] = ["code_reviewer"]
    context["required_action_tools"] = ["read_file", "update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["verification_scope"] = {
        "workspace": ["agent_output/main.py"],
        "provided_context": [],
        "declared_interfaces": ["read_file", "update_issue_status"],
    }

    result = await executor.execute_turn(
        _issue(),
        role,
        model,
        toolbox,
        context,
    )
    assert result.success is True
    assert model.calls == 2
    assert len(toolbox.calls) == 2
    assert toolbox.calls[0][1]["path"] == "agent_output/main.py"


@pytest.mark.asyncio
async def test_turn_executor_hallucination_scope_contract_fails_after_reprompt(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "read_file", "args": {"path": "agent_output/not_allowed.py"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
            '{"tool": "read_file", "args": {"path": "agent_output/not_allowed.py"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="REV",
        summary="code_reviewer",
        description="Review code",
        tools=["read_file", "update_issue_status"],
    )
    context = _context()
    context["role"] = "code_reviewer"
    context["roles"] = ["code_reviewer"]
    context["required_action_tools"] = ["read_file", "update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["verification_scope"] = {
        "workspace": ["agent_output/main.py"],
        "provided_context": [],
        "declared_interfaces": ["read_file", "update_issue_status"],
    }

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is False
    assert model.calls == 2
    assert len(toolbox.calls) == 0
    assert "hallucination scope contract not met after corrective reprompt" in (result.error or "")


@pytest.mark.asyncio
async def test_turn_executor_hallucination_strict_grounding_ignores_non_json_residue(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}\nI assume this should work.',
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}\nI assume this should work.',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="REV",
        summary="code_reviewer",
        description="Review code",
        tools=["update_issue_status"],
    )
    context = _context()
    context["role"] = "code_reviewer"
    context["roles"] = ["code_reviewer"]
    context["required_action_tools"] = ["update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["verification_scope"] = {
        "workspace": [],
        "provided_context": [],
        "declared_interfaces": ["update_issue_status"],
        "strict_grounding": True,
    }

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is True
    assert model.calls == 1
    assert len(toolbox.calls) == 1


@pytest.mark.asyncio
async def test_turn_executor_hallucination_strict_grounding_ignores_json_payload_content(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "write_file", "args": {"path": "agent_output/main.py", "content": "value = \\"maybe\\"\\n"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="COD",
        summary="coder",
        description="Write code",
        tools=["write_file", "update_issue_status"],
    )
    context = _context()
    context["role"] = "coder"
    context["roles"] = ["coder"]
    context["required_action_tools"] = ["write_file", "update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["required_write_paths"] = ["agent_output/main.py"]
    context["verification_scope"] = {
        "workspace": ["agent_output/main.py"],
        "provided_context": [],
        "declared_interfaces": ["write_file", "update_issue_status"],
        "strict_grounding": True,
    }

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is True
    assert model.calls == 1
    assert len(toolbox.calls) == 2
    assert toolbox.calls[0][0] == "write_file"
    assert toolbox.calls[1][0] == "update_issue_status"


@pytest.mark.asyncio
async def test_turn_executor_hallucination_contradiction_detects_forbidden_phrase(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}\nNo tests were run.',
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}\nNo tests were run.',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="REV",
        summary="code_reviewer",
        description="Review code",
        tools=["update_issue_status"],
    )
    context = _context()
    context["role"] = "code_reviewer"
    context["roles"] = ["code_reviewer"]
    context["required_action_tools"] = ["update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["verification_scope"] = {
        "workspace": [],
        "provided_context": [],
        "declared_interfaces": ["update_issue_status"],
        "forbidden_phrases": ["no tests were run"],
    }

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is False
    assert model.calls == 2
    assert len(toolbox.calls) == 0
    assert "hallucination scope contract not met after corrective reprompt" in (result.error or "")


@pytest.mark.asyncio
async def test_turn_executor_hallucination_context_partition_enforces_active_context_only(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "get_issue_context", "args": {"section": "legacy-architecture-notes"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
            '{"tool": "get_issue_context", "args": {"section": "legacy-architecture-notes"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="REV",
        summary="code_reviewer",
        description="Review code",
        tools=["get_issue_context", "update_issue_status"],
    )
    context = _context()
    context["role"] = "code_reviewer"
    context["roles"] = ["code_reviewer"]
    context["required_action_tools"] = ["get_issue_context", "update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["verification_scope"] = {
        "workspace": [],
        "active_context": ["current-prd"],
        "passive_context": ["legacy-architecture-notes"],
        "archived_context": [],
        "declared_interfaces": ["get_issue_context", "update_issue_status"],
    }

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is False
    assert model.calls == 2
    assert len(toolbox.calls) == 0
    assert "hallucination scope contract not met after corrective reprompt" in (result.error or "")


@pytest.mark.asyncio
async def test_turn_executor_hallucination_context_budget_exceeded_fails_after_reprompt(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="REV",
        summary="code_reviewer",
        description="Review code",
        tools=["update_issue_status"],
    )
    context = _context()
    context["role"] = "code_reviewer"
    context["roles"] = ["code_reviewer"]
    context["required_action_tools"] = ["update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["verification_scope"] = {
        "workspace": [],
        "active_context": ["ctx-1", "ctx-2", "ctx-3"],
        "passive_context": [],
        "archived_context": [],
        "declared_interfaces": ["update_issue_status"],
        "max_active_context_items": 2,
    }

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is False
    assert model.calls == 2
    assert len(toolbox.calls) == 0
    assert "hallucination scope contract not met after corrective reprompt" in (result.error or "")


@pytest.mark.asyncio
async def test_turn_executor_hallucination_context_budget_within_limit_succeeds(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="REV",
        summary="code_reviewer",
        description="Review code",
        tools=["update_issue_status"],
    )
    context = _context()
    context["role"] = "code_reviewer"
    context["roles"] = ["code_reviewer"]
    context["required_action_tools"] = ["update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["verification_scope"] = {
        "workspace": [],
        "active_context": ["ctx-1", "ctx-2"],
        "passive_context": [],
        "archived_context": [],
        "declared_interfaces": ["update_issue_status"],
        "max_active_context_items": 2,
    }

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is True
    assert model.calls == 1
    assert len(toolbox.calls) == 1


def test_build_corrective_instruction_includes_rule_specific_hints(tmp_path):
    """Layer: unit. Verifies corrective prompt hints remain available through the explicit builder collaborator."""
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    instruction = executor.corrective_prompt_builder.build_corrective_instruction(
        [
            {
                "reason": "security_scope_contract_not_met",
                "violations": [
                    {"rule_id": "SECURITY.PATH_TRAVERSAL", "evidence": "../secret.txt"},
                ],
            }
        ],
        {
            "required_action_tools": ["update_issue_status"],
            "required_statuses": ["code_review"],
        },
    )
    assert "Rule-specific fixes:" in instruction
    assert "SECURITY.PATH_TRAVERSAL" in instruction
    assert "../secret.txt" in instruction


@pytest.mark.asyncio
async def test_turn_executor_security_scope_rejects_path_traversal(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "read_file", "args": {"path": "../secrets.txt"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
            '{"tool": "read_file", "args": {"path": "../secrets.txt"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="REV",
        summary="code_reviewer",
        description="Review code",
        tools=["read_file", "update_issue_status"],
    )
    context = _context()
    context["role"] = "code_reviewer"
    context["roles"] = ["code_reviewer"]
    context["required_action_tools"] = ["read_file", "update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["verification_scope"] = {
        "workspace": [],
        "provided_context": [],
        "declared_interfaces": ["read_file", "update_issue_status"],
        "enforce_path_hardening": True,
    }

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is False
    assert model.calls == 2
    assert len(toolbox.calls) == 0
    assert "security scope contract not met after corrective reprompt" in (result.error or "")


@pytest.mark.asyncio
async def test_turn_executor_security_scope_recovers_after_reprompt(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "read_file", "args": {"path": "C:/Windows/System32/config"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
            '{"tool": "read_file", "args": {"path": "agent_output/main.py"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="REV",
        summary="code_reviewer",
        description="Review code",
        tools=["read_file", "update_issue_status"],
    )
    context = _context()
    context["role"] = "code_reviewer"
    context["roles"] = ["code_reviewer"]
    context["required_action_tools"] = ["read_file", "update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["verification_scope"] = {
        "workspace": [],
        "provided_context": [],
        "declared_interfaces": ["read_file", "update_issue_status"],
        "enforce_path_hardening": True,
    }

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is True
    assert model.calls == 2
    assert len(toolbox.calls) == 2
    assert toolbox.calls[0][1]["path"] == "agent_output/main.py"


@pytest.mark.asyncio
async def test_turn_executor_consistency_scope_rejects_extra_prose(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            'Here is the result.\n{"tool": "update_issue_status", "args": {"status": "code_review"}}',
            'Here is the result.\n{"tool": "update_issue_status", "args": {"status": "code_review"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="REV",
        summary="code_reviewer",
        description="Review code",
        tools=["update_issue_status"],
    )
    context = _context()
    context["role"] = "code_reviewer"
    context["roles"] = ["code_reviewer"]
    context["required_action_tools"] = ["update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["verification_scope"] = {
        "workspace": [],
        "provided_context": [],
        "declared_interfaces": ["update_issue_status"],
        "consistency_tool_calls_only": True,
    }

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is False
    assert model.calls == 2
    assert len(toolbox.calls) == 0
    assert "consistency scope contract not met after corrective reprompt" in (result.error or "")


@pytest.mark.asyncio
async def test_turn_executor_consistency_scope_recovers_after_reprompt(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            'Done.\n{"tool": "update_issue_status", "args": {"status": "code_review"}}',
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="REV",
        summary="code_reviewer",
        description="Review code",
        tools=["update_issue_status"],
    )
    context = _context()
    context["role"] = "code_reviewer"
    context["roles"] = ["code_reviewer"]
    context["required_action_tools"] = ["update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["verification_scope"] = {
        "workspace": [],
        "provided_context": [],
        "declared_interfaces": ["update_issue_status"],
        "consistency_tool_calls_only": True,
    }

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is True
    assert model.calls == 2
    assert len(toolbox.calls) == 1
    assert toolbox.calls[0][1]["status"] == "code_review"


@pytest.mark.asyncio
async def test_turn_executor_consistency_scope_allows_markdown_json_fences(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '```json\n{"tool": "update_issue_status", "args": {"status": "code_review"}}\n```',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="REV",
        summary="code_reviewer",
        description="Review code",
        tools=["update_issue_status"],
    )
    context = _context()
    context["role"] = "code_reviewer"
    context["roles"] = ["code_reviewer"]
    context["required_action_tools"] = ["update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["verification_scope"] = {
        "workspace": [],
        "provided_context": [],
        "declared_interfaces": ["update_issue_status"],
        "consistency_tool_calls_only": True,
    }

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is True
    assert model.calls == 1
    assert len(toolbox.calls) == 1
    assert toolbox.calls[0][1]["status"] == "code_review"


@pytest.mark.asyncio
async def test_turn_executor_consistency_scope_allows_json_array_envelope(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '[{"tool": "update_issue_status", "args": {"status": "code_review"}}]',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="REV",
        summary="code_reviewer",
        description="Review code",
        tools=["update_issue_status"],
    )
    context = _context()
    context["role"] = "code_reviewer"
    context["roles"] = ["code_reviewer"]
    context["required_action_tools"] = ["update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["verification_scope"] = {
        "workspace": [],
        "provided_context": [],
        "declared_interfaces": ["update_issue_status"],
        "consistency_tool_calls_only": True,
    }

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is True
    assert model.calls == 1
    assert len(toolbox.calls) == 1
    assert toolbox.calls[0][1]["status"] == "code_review"


@pytest.mark.asyncio
async def test_turn_executor_consistency_scope_allows_comma_separated_objects(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "write_file", "args": {"path": "agent_output/review.md", "content": "ok"}},'
            '\n{"tool": "update_issue_status", "args": {"status": "code_review"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="REV",
        summary="code_reviewer",
        description="Review code",
        tools=["write_file", "update_issue_status"],
    )
    context = _context()
    context["role"] = "code_reviewer"
    context["roles"] = ["code_reviewer"]
    context["required_action_tools"] = ["write_file", "update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["verification_scope"] = {
        "workspace": [],
        "provided_context": [],
        "declared_interfaces": ["write_file", "update_issue_status"],
        "consistency_tool_calls_only": True,
    }

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is True
    assert model.calls == 1
    assert len(toolbox.calls) == 2
    assert toolbox.calls[1][1]["status"] == "code_review"


@pytest.mark.asyncio
async def test_turn_executor_architecture_contract_recovers_after_reprompt(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "write_file", "args": {"path": "agent_output/design.txt", "content": "plain text design"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
            '{"tool": "write_file", "args": {"path": "agent_output/design.txt", "content": "{\\"recommendation\\": \\"microservices\\", \\"confidence\\": 0.82, \\"evidence\\": {\\"estimated_domains\\": 4, \\"external_integrations\\": 3, \\"independent_scaling_needs\\": \\"high\\", \\"deployment_complexity\\": \\"high\\", \\"team_parallelism\\": \\"multi-team\\", \\"operational_maturity\\": \\"med\\"}}"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="ARC",
        summary="architect",
        description="Design architecture",
        tools=["write_file", "update_issue_status"],
    )
    context = _context()
    context["role"] = "architect"
    context["roles"] = ["architect"]
    context["required_action_tools"] = ["write_file", "update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["architecture_decision_required"] = True
    context["architecture_mode"] = "architect_decides"
    context["architecture_decision_path"] = "agent_output/design.txt"
    context["architecture_allowed_patterns"] = ["monolith", "microservices"]

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is True
    assert model.calls == 2
    assert len(toolbox.calls) == 2


@pytest.mark.asyncio
async def test_turn_executor_architecture_contract_enforces_forced_pattern(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "write_file", "args": {"path": "agent_output/design.txt", "content": "{\\"recommendation\\": \\"monolith\\", \\"confidence\\": 0.9, \\"evidence\\": {\\"estimated_domains\\": 1, \\"external_integrations\\": 1, \\"independent_scaling_needs\\": \\"low\\", \\"deployment_complexity\\": \\"low\\", \\"team_parallelism\\": \\"single\\", \\"operational_maturity\\": \\"low\\"}}"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
            '{"tool": "write_file", "args": {"path": "agent_output/design.txt", "content": "{\\"recommendation\\": \\"monolith\\", \\"confidence\\": 0.9, \\"evidence\\": {\\"estimated_domains\\": 1, \\"external_integrations\\": 1, \\"independent_scaling_needs\\": \\"low\\", \\"deployment_complexity\\": \\"low\\", \\"team_parallelism\\": \\"single\\", \\"operational_maturity\\": \\"low\\"}}"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="ARC",
        summary="architect",
        description="Design architecture",
        tools=["write_file", "update_issue_status"],
    )
    context = _context()
    context["role"] = "architect"
    context["roles"] = ["architect"]
    context["required_action_tools"] = ["write_file", "update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["architecture_decision_required"] = True
    context["architecture_mode"] = "force_microservices"
    context["architecture_decision_path"] = "agent_output/design.txt"
    context["architecture_allowed_patterns"] = ["monolith", "microservices"]
    context["architecture_forced_pattern"] = "microservices"

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is False
    assert model.calls == 2
    assert "architecture decision contract not met" in (result.error or "")


@pytest.mark.asyncio
async def test_turn_executor_architecture_contract_enforces_forced_frontend_framework(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "write_file", "args": {"path": "agent_output/design.txt", "content": "{\\"recommendation\\": \\"microservices\\", \\"frontend_framework\\": \\"react\\", \\"confidence\\": 0.9, \\"evidence\\": {\\"estimated_domains\\": 4, \\"external_integrations\\": 3, \\"independent_scaling_needs\\": \\"high\\", \\"deployment_complexity\\": \\"high\\", \\"team_parallelism\\": \\"multi-team\\", \\"operational_maturity\\": \\"med\\"}}"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
            '{"tool": "write_file", "args": {"path": "agent_output/design.txt", "content": "{\\"recommendation\\": \\"microservices\\", \\"frontend_framework\\": \\"react\\", \\"confidence\\": 0.9, \\"evidence\\": {\\"estimated_domains\\": 4, \\"external_integrations\\": 3, \\"independent_scaling_needs\\": \\"high\\", \\"deployment_complexity\\": \\"high\\", \\"team_parallelism\\": \\"multi-team\\", \\"operational_maturity\\": \\"med\\"}}"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="ARC",
        summary="architect",
        description="Design architecture",
        tools=["write_file", "update_issue_status"],
    )
    context = _context()
    context["role"] = "architect"
    context["roles"] = ["architect"]
    context["required_action_tools"] = ["write_file", "update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["architecture_decision_required"] = True
    context["architecture_mode"] = "architect_decides"
    context["architecture_decision_path"] = "agent_output/design.txt"
    context["architecture_allowed_patterns"] = ["monolith", "microservices"]
    context["frontend_framework_allowed"] = ["vue", "react", "angular"]
    context["frontend_framework_forced"] = "angular"

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is False
    assert model.calls == 2
    assert "architecture decision contract not met" in (result.error or "")


@pytest.mark.asyncio
async def test_turn_executor_architecture_contract_allows_relaxed_json_like_content(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "write_file", "args": {"path": "agent_output/design.txt", "content": "{\\"recommendation\\": \\"monolith\\", \\"confidence\\": 0.9, \\"evidence\\": {\\"estimated_domains\\": 1, \\"external_integrations\\": 0, \\"independent_scaling_needs\\": false, \\"deployment_complexity\\": low, \\"team_parallelism\\": high, \\"operational_maturity\\": high}, \\"frontend_framework\\": \\"vue\\"}"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="ARC",
        summary="architect",
        description="Design architecture",
        tools=["write_file", "update_issue_status"],
    )
    context = _context()
    context["role"] = "architect"
    context["roles"] = ["architect"]
    context["required_action_tools"] = ["write_file", "update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["architecture_decision_required"] = True
    context["architecture_mode"] = "force_monolith"
    context["architecture_decision_path"] = "agent_output/design.txt"
    context["architecture_allowed_patterns"] = ["monolith", "microservices"]
    context["architecture_forced_pattern"] = "monolith"
    context["frontend_framework_allowed"] = ["vue"]
    context["frontend_framework_forced"] = "vue"
    context["verification_scope"] = {
        "workspace": [],
        "provided_context": [],
        "declared_interfaces": ["write_file", "update_issue_status"],
        "consistency_tool_calls_only": True,
    }

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is True
    assert model.calls == 1
    assert len(toolbox.calls) == 2
    assert toolbox.calls[0][0] == "write_file"
    assert toolbox.calls[1][1]["status"] == "code_review"


@pytest.mark.asyncio
async def test_turn_executor_autofills_required_status_tool_call(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "write_file", "args": {"path": "agent_output/design.txt", "content": "{\\"recommendation\\": \\"monolith\\", \\"confidence\\": 0.9, \\"evidence\\": {\\"estimated_domains\\": 1, \\"external_integrations\\": 0, \\"independent_scaling_needs\\": false, \\"deployment_complexity\\": \\"low\\", \\"team_parallelism\\": \\"low\\", \\"operational_maturity\\": \\"high\\"}, \\"frontend_framework\\": \\"vue\\"}"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="ARC",
        summary="architect",
        description="Design architecture",
        tools=["write_file", "update_issue_status"],
    )
    context = _context()
    context["role"] = "architect"
    context["roles"] = ["architect"]
    context["required_action_tools"] = ["write_file", "update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["architecture_decision_required"] = True
    context["architecture_mode"] = "force_monolith"
    context["architecture_decision_path"] = "agent_output/design.txt"
    context["architecture_allowed_patterns"] = ["monolith", "microservices"]
    context["architecture_forced_pattern"] = "monolith"
    context["frontend_framework_allowed"] = ["vue"]
    context["frontend_framework_forced"] = "vue"

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is True
    assert model.calls == 1
    assert len(toolbox.calls) == 2
    assert toolbox.calls[0][0] == "write_file"
    assert toolbox.calls[1][0] == "update_issue_status"
    assert toolbox.calls[1][1]["status"] == "code_review"


@pytest.mark.asyncio
async def test_turn_executor_autofills_integrity_guard_done_when_runtime_passed(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "read_file", "args": {"path": "agent_output/requirements.txt"}}\n'
            '{"tool": "read_file", "args": {"path": "agent_output/design.txt"}}\n'
            '{"tool": "read_file", "args": {"path": "agent_output/main.py"}}\n'
            '{"tool": "read_file", "args": {"path": "agent_output/verification/runtime_verification.json"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="GRD",
        summary="integrity_guard",
        description="Final gate",
        tools=["read_file", "update_issue_status"],
    )
    context = _context()
    context["role"] = "integrity_guard"
    context["roles"] = ["integrity_guard"]
    context["required_action_tools"] = ["read_file", "update_issue_status"]
    context["required_statuses"] = ["done", "blocked"]
    context["required_read_paths"] = [
        "agent_output/requirements.txt",
        "agent_output/design.txt",
        "agent_output/main.py",
        "agent_output/verification/runtime_verification.json",
    ]
    context["runtime_verifier_ok"] = True

    result = await executor.execute_turn(_guard_issue(), role, model, toolbox, context)
    assert result.success is True
    assert model.calls == 1
    assert len(toolbox.calls) == 5
    assert toolbox.calls[-1][0] == "update_issue_status"
    assert toolbox.calls[-1][1]["status"] == "done"
