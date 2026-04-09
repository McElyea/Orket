from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.agents import agent as agent_module
from orket.agents.agent import Agent
from orket.application.middleware import TurnLifecycleInterceptors
from orket.application.workflows.turn_executor import TurnExecutor
from orket.application.workflows.turn_tool_dispatcher import ToolDispatcher
from orket.core.domain.execution import ExecutionTurn, ToolCall, ToolCallErrorClass
from orket.core.domain.state_machine import StateMachine
from orket.core.policies.tool_gate import ToolGate
from orket.extensions.contracts import RunAction
from orket.extensions.runtime import ExtensionEngineAdapter, RunContext
from orket.runtime.execution.execution_pipeline_card_dispatch import ExecutionPipelineCardDispatchMixin
from orket.schema import CardStatus, IssueConfig, RoleConfig

OUTPUT_PATH = REPO_ROOT / "benchmarks" / "results" / "security" / "tool_gate_audit.json"
PROOF_REF = "python scripts/security/build_tool_gate_audit.py --strict"


class _MissingConfigLoader:
    dialects: list[str] = []

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def load_asset(self, category: str, name: str, _schema: Any) -> Any:
        if category == "dialects":
            self.dialects.append(name)
        raise FileNotFoundError(name)


class _DenyAllToolGate(ToolGate):
    def __init__(self, workspace_root: Path, *, reason: str = "deny_all:write_file") -> None:
        super().__init__(organization=None, workspace_root=workspace_root)
        self.reason = reason

    async def validate(
        self,
        tool_name: str,
        args: dict[str, Any],
        context: dict[str, Any],
        roles: list[str],
    ) -> str | None:
        _ = args, context, roles
        return f"{self.reason}:{tool_name}"


class _WritingToolbox:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root
        self.calls = 0

    async def execute(self, tool_name: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        _ = context
        self.calls += 1
        target = Path(str(args["path"]))
        if not target.is_absolute():
            target = self.workspace_root / target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(args.get("content", "")), encoding="utf-8")
        return {"ok": True, "tool": tool_name, "path": str(target)}


class _Model:
    def __init__(self, tool_name: str, tool_args: dict[str, Any]) -> None:
        self.tool_name = tool_name
        self.tool_args = dict(tool_args)

    async def complete(self, _messages: list[dict[str, str]]) -> dict[str, Any]:
        return {
            "content": json.dumps({"tool": self.tool_name, "args": self.tool_args}),
            "raw": {"total_tokens": 1},
        }


class _RunCardHarness(ExecutionPipelineCardDispatchMixin):
    def __init__(self, workspace_root: Path, tool_gate: ToolGate, tool_args: dict[str, Any]) -> None:
        self.workspace = workspace_root
        self._tool_gate = tool_gate
        self._tool_args = dict(tool_args)
        self.toolbox = _WritingToolbox(workspace_root)
        self.last_result: Any | None = None

    async def initialize(self) -> None:
        return None

    async def _find_parent_epic(self, issue_id: str) -> tuple[Any, str | None, Any]:
        _ = issue_id
        return object(), "demo-epic", object()

    async def _resolve_run_card_target(self, card_id: str) -> tuple[str, str | None]:
        _ = card_id
        return "issue", "demo-epic"

    async def _run_epic_collection_entry(
        self,
        collection_name: str,
        build_id: str | None = None,
        session_id: str | None = None,
        driver_steered: bool = False,
        model_override: str | None = None,
    ) -> dict[str, Any]:
        raise AssertionError(f"Unexpected epic collection entry: {collection_name}")

    async def _run_issue_entry(
        self,
        issue_id: str,
        build_id: str | None = None,
        session_id: str | None = None,
        driver_steered: bool = False,
        parent_epic_name: str | None = None,
        target_issue_id: str | None = None,
        model_override: str | None = None,
    ) -> dict[str, Any]:
        _ = build_id, session_id, driver_steered, parent_epic_name, target_issue_id, model_override
        self.last_result = await _execute_turn(
            workspace_root=self.workspace,
            tool_gate=self._tool_gate,
            tool_args=self._tool_args,
            toolbox=self.toolbox,
            issue_id=issue_id,
        )
        return {
            "success": self.last_result.success,
            "error": self.last_result.error,
            "violations": list(self.last_result.violations),
        }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate the canonical tool gate audit artifact.")
    parser.add_argument("--out", default=str(OUTPUT_PATH), help="Stable output JSON path.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when required path results drift.")
    return parser


def _context(issue_id: str) -> dict[str, Any]:
    return {
        "session_id": "sess-1",
        "issue_id": issue_id,
        "role": "developer",
        "roles": ["developer"],
        "current_status": "in_progress",
        "selected_model": "dummy-model",
        "turn_index": 1,
        "history": [],
    }


def _issue(issue_id: str) -> IssueConfig:
    return IssueConfig(id=issue_id, summary="Implement feature", seat="developer", status=CardStatus.IN_PROGRESS)


def _role() -> RoleConfig:
    return RoleConfig(id="DEV", summary="developer", description="Build code", tools=["write_file"])


async def _execute_turn(
    *,
    workspace_root: Path,
    tool_gate: ToolGate,
    tool_args: dict[str, Any],
    toolbox: _WritingToolbox,
    issue_id: str,
) -> Any:
    executor = TurnExecutor(
        state_machine=StateMachine(),
        tool_gate=tool_gate,
        workspace=workspace_root,
        middleware=TurnLifecycleInterceptors([]),
    )
    return await executor.execute_turn(
        _issue(issue_id),
        _role(),
        _Model("write_file", tool_args),
        toolbox,
        _context(issue_id),
    )


def _dispatcher(workspace_root: Path, tool_gate: ToolGate) -> ToolDispatcher:
    def _load_replay_tool_result(**_kwargs: Any) -> dict[str, Any] | None:
        return None

    def _persist_tool_result(**_kwargs: Any) -> None:
        return None

    def _load_operation_result(**_kwargs: Any) -> dict[str, Any] | None:
        return None

    def _persist_operation_result(**_kwargs: Any) -> None:
        return None

    def _append_protocol_receipt(**kwargs: Any) -> dict[str, Any]:
        return dict(kwargs.get("receipt") or {})

    return ToolDispatcher(
        tool_gate=tool_gate,
        middleware=TurnLifecycleInterceptors([]),
        workspace=workspace_root,
        append_memory_event=lambda *args, **kwargs: None,
        hash_payload=lambda payload: "hash",
        load_replay_tool_result=_load_replay_tool_result,
        persist_tool_result=_persist_tool_result,
        load_operation_result=_load_operation_result,
        persist_operation_result=_persist_operation_result,
        append_protocol_receipt=_append_protocol_receipt,
        tool_validation_error_factory=lambda violations: RuntimeError(str(violations)),
    )


def _row(
    *,
    dispatch_path: str,
    entrypoint: str,
    supported: bool,
    path_status: str,
    gate_type: str,
    deny_all_expected_result: str,
    observed_result: str,
    side_effect_observed: bool,
    legacy_status: str = "",
    non_runtime_reason: str = "",
    out_of_scope_lane: str = "",
    notes: str = "",
) -> dict[str, Any]:
    return {
        "dispatch_path": dispatch_path,
        "entrypoint": entrypoint,
        "supported": supported,
        "path_status": path_status,
        "gate_type": gate_type,
        "deny_all_expected_result": deny_all_expected_result,
        "observed_result": observed_result,
        "proof_ref": PROOF_REF,
        "legacy_status": legacy_status,
        "non_runtime_reason": non_runtime_reason,
        "out_of_scope_lane": out_of_scope_lane,
        "side_effect_observed": side_effect_observed,
        "notes": notes,
    }


async def _collect_rows(project_root: Path) -> list[dict[str, Any]]:
    workspace_root = project_root / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    deny_gate = _DenyAllToolGate(workspace_root)
    tool_args = {"path": "agent_output/denied.txt", "content": "x"}

    direct_turn_toolbox = _WritingToolbox(workspace_root)
    direct_turn_result = await _execute_turn(
        workspace_root=workspace_root,
        tool_gate=deny_gate,
        tool_args=tool_args,
        toolbox=direct_turn_toolbox,
        issue_id="ISSUE-1",
    )

    direct_dispatch_toolbox = _WritingToolbox(workspace_root)
    direct_dispatcher = _dispatcher(workspace_root, deny_gate)
    direct_dispatch_result = "blocked"
    try:
        await direct_dispatcher.execute_tools(
            turn=ExecutionTurn(
                role="developer",
                issue_id="ISSUE-1",
                content="",
                tool_calls=[ToolCall(tool="write_file", args=tool_args)],
            ),
            toolbox=direct_dispatch_toolbox,
            context=_context("ISSUE-1"),
            issue=None,
        )
        direct_dispatch_result = "allowed"
    except RuntimeError:
        direct_dispatch_result = "blocked"

    run_card_harness = _RunCardHarness(workspace_root=workspace_root, tool_gate=deny_gate, tool_args=tool_args)
    run_card_payload = await run_card_harness.run_card("ISSUE-1")
    run_card_result = (
        "blocked"
        if (not run_card_payload["success"] and run_card_harness.toolbox.calls == 0)
        else "allowed"
    )

    import orket.extensions.runtime as extension_runtime_module

    class _EngineProxy:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            return None

        async def run_card(self, card_id: str, **kwargs: Any) -> dict[str, Any]:
            _ = kwargs
            return await extension_harness.run_card(card_id)

    original_engine = extension_runtime_module.OrchestrationEngine
    extension_runtime_module.OrchestrationEngine = _EngineProxy
    try:
        extension_harness = _RunCardHarness(workspace_root=workspace_root, tool_gate=deny_gate, tool_args=tool_args)
        adapter = ExtensionEngineAdapter(RunContext(workspace=workspace_root, department="core"))
        extension_payload = await adapter.execute_action(
            RunAction(op="run_issue", target="ISSUE-9", params={"session_id": "sess-1"})
        )
    finally:
        extension_runtime_module.OrchestrationEngine = original_engine
    extension_result = (
        "blocked"
        if (not extension_payload["transcript"]["success"] and extension_harness.toolbox.calls == 0)
        else "allowed"
    )

    agent_calls: list[dict[str, Any]] = []
    original_loader = agent_module.ConfigLoader
    agent_module.ConfigLoader = _MissingConfigLoader
    try:
        async def _tool(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
            _ = context
            agent_calls.append(dict(args))
            return {"ok": True}

        class _ToolProvider:
            model = "unknown-7b"

            async def complete(
                self,
                messages: list[dict[str, str]],
                runtime_context: dict[str, Any] | None = None,
            ) -> str:
                _ = messages, runtime_context
                return json.dumps({"tool": "write_file", "args": tool_args})

        agent = Agent(
            "coder",
            "description",
            {"write_file": _tool},
            _ToolProvider(),
            config_root=workspace_root,
            strict_config=False,
        )
        agent_turn = await agent.run(
            {"description": "do work"},
            {"issue_id": "ISSUE-1", "roles": ["coder"]},
            workspace_root,
        )
    finally:
        agent_module.ConfigLoader = original_loader
    agent_result = (
        "blocked"
        if (
            not agent_calls
            and agent_turn.tool_calls
            and agent_turn.tool_calls[0].error_class is ToolCallErrorClass.GATE_BLOCKED
        )
        else "allowed"
    )

    return [
        _row(
            dispatch_path="run_card.turn_executor.tool_dispatcher",
            entrypoint="orket/runtime/execution/execution_pipeline_card_dispatch.py::ExecutionPipelineCardDispatchMixin.run_card",
            supported=True,
            path_status="primary",
            gate_type="composed",
            deny_all_expected_result="blocked",
            observed_result=run_card_result,
            side_effect_observed=bool(run_card_harness.toolbox.calls),
        ),
        _row(
            dispatch_path="direct_turn_executor_execute_turn",
            entrypoint="orket/application/workflows/turn_executor.py::TurnExecutor.execute_turn",
            supported=False,
            path_status="internal-only",
            gate_type="composed",
            deny_all_expected_result="blocked",
            observed_result="blocked" if (not direct_turn_result.success and direct_turn_toolbox.calls == 0) else "allowed",
            side_effect_observed=bool(direct_turn_toolbox.calls),
            non_runtime_reason="Authoritative construction and delegation seam, not an independent public runtime path.",
        ),
        _row(
            dispatch_path="direct_tool_dispatcher_execute_tools",
            entrypoint="orket/application/workflows/turn_tool_dispatcher.py::ToolDispatcher.execute_tools",
            supported=False,
            path_status="internal-only",
            gate_type="composed",
            deny_all_expected_result="blocked",
            observed_result=direct_dispatch_result,
            side_effect_observed=bool(direct_dispatch_toolbox.calls),
            non_runtime_reason="Authoritative internal gate seam, not a separate supported public path.",
        ),
        _row(
            dispatch_path="agent_run_direct_tool_execution",
            entrypoint="orket/agents/agent.py::Agent.run",
            supported=False,
            path_status="legacy-compatibility",
            gate_type="legacy_fail_closed",
            deny_all_expected_result="blocked",
            observed_result=agent_result,
            side_effect_observed=bool(agent_calls),
            legacy_status="retained_fail_closed",
            notes="Legacy compatibility surface now blocks before any direct tool call when tool_gate authority is missing.",
        ),
        _row(
            dispatch_path="direct_toolbox_execute",
            entrypoint="orket/tools.py::ToolBox.execute",
            supported=False,
            path_status="internal-only",
            gate_type="helper_only",
            deny_all_expected_result="blocked_before_reachability",
            observed_result="blocked_before_reachability",
            side_effect_observed=False,
            non_runtime_reason="Helper-only execution surface reached from the dispatcher path, not an independent runtime gate story.",
        ),
        _row(
            dispatch_path="direct_card_family_method_invocation",
            entrypoint="orket/runtime/execution/execution_pipeline_card_dispatch.py::ExecutionPipelineCardDispatchMixin._run_issue_entry",
            supported=False,
            path_status="internal-only",
            gate_type="implementation_detail",
            deny_all_expected_result="blocked_before_reachability",
            observed_result="blocked_before_reachability",
            side_effect_observed=False,
            non_runtime_reason="Card-family methods are tool implementations; gate authority happens before invocation.",
        ),
        _row(
            dispatch_path="extension_engine_action_normalized_run_card",
            entrypoint="orket/extensions/runtime.py::ExtensionEngineAdapter.execute_action",
            supported=True,
            path_status="primary",
            gate_type="composed",
            deny_all_expected_result="blocked",
            observed_result=extension_result,
            side_effect_observed=bool(extension_harness.toolbox.calls),
            notes="Primary only because extension actions normalize back into run_card before tool execution.",
        ),
        _row(
            dispatch_path="sdk_capability_registry_invocation",
            entrypoint="orket/extensions/workload_executor.py::WorkloadExecutor.execute",
            supported=False,
            path_status="out-of-scope",
            gate_type="sdk_capability_authorization",
            deny_all_expected_result="out_of_scope",
            observed_result="out_of_scope",
            side_effect_observed=False,
            out_of_scope_lane="docs/specs/EXTENSION_CAPABILITY_AUTHORIZATION_V1.md",
            notes="SDK capability invocation is governed by the separate capability-authorization contract, not Tool Gate Enforcement.",
        ),
    ]


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="orket-tool-gate-audit-") as temp_dir:
        rows = asyncio.run(_collect_rows(Path(temp_dir).resolve()))
    payload = {
        "schema_version": "tool_gate_audit.v1",
        "gate_surface": "governed_turn_tool_gate_v1",
        "paths": rows,
    }
    persisted = write_payload_with_diff_ledger(Path(str(args.out)).resolve(), payload)
    if bool(args.strict):
        required_rows = {
            "run_card.turn_executor.tool_dispatcher",
            "agent_run_direct_tool_execution",
            "extension_engine_action_normalized_run_card",
        }
        observed_rows = {row["dispatch_path"] for row in rows}
        if required_rows - observed_rows:
            return 1
        for row in rows:
            if row["dispatch_path"] in required_rows:
                if row["observed_result"] != "blocked" or bool(row["side_effect_observed"]):
                    return 1
    print(json.dumps(persisted, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
