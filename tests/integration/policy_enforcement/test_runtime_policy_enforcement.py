from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.application.middleware import TurnLifecycleInterceptors
from orket.application.workflows.turn_tool_dispatcher import ToolDispatcher
from orket.core.domain.execution import ExecutionTurn, ToolCall
from orket.core.policies.tool_gate import ToolGate
from orket.interfaces.api import app
from orket.runtime.execution_pipeline import ExecutionPipeline
from orket.runtime.source_attribution_policy import (
    source_attribution_policy_snapshot,
    validate_source_attribution_policy,
)
from orket.runtime.trust_language_review_policy import (
    trust_language_review_policy_snapshot,
    validate_trust_language_review_policy,
)
from orket.runtime.workspace_hygiene_rules import (
    validate_workspace_hygiene_rules,
    workspace_hygiene_rules_snapshot,
)
import orket.runtime.run_start_contract_artifacts as run_start_contract_artifacts
import orket.runtime.run_start_artifacts as run_start_artifacts

client = TestClient(app)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_epic_assets(root: Path, epic_id: str, *, environment_payload: dict[str, Any] | None = None) -> None:
    _write_json(
        root / "model" / "core" / "teams" / "standard.json",
        {
            "name": "standard",
            "seats": {
                "lead_architect": {
                    "name": "Lead",
                    "roles": ["lead_architect"],
                }
            },
        },
    )
    _write_json(
        root / "model" / "core" / "environments" / "standard.json",
        environment_payload
        or {
            "name": "standard",
            "model": "test-model",
            "temperature": 0.0,
        },
    )
    _write_json(
        root / "model" / "core" / "epics" / f"{epic_id}.json",
        {
            "id": epic_id,
            "name": epic_id,
            "type": "epic",
            "team": "standard",
            "environment": "standard",
            "description": "Policy enforcement test",
            "architecture_governance": {"idesign": False, "pattern": "Standard"},
            "issues": [
                {
                    "id": "ISSUE-1",
                    "summary": "Do work",
                    "seat": "lead_architect",
                    "priority": "High",
                    "depends_on": [],
                }
            ],
        },
    )


def _override_snapshot_factory(
    monkeypatch: pytest.MonkeyPatch,
    *,
    artifact_key: str,
    factory: Any,
) -> None:
    updated_defs = []
    for key, filename, snapshot_factory, error_code in run_start_contract_artifacts.CONTRACT_SNAPSHOT_DEFS:
        if key == artifact_key:
            updated_defs.append((key, filename, factory, error_code))
        else:
            updated_defs.append((key, filename, snapshot_factory, error_code))
    updated_defs_tuple = tuple(updated_defs)
    monkeypatch.setattr(run_start_contract_artifacts, "CONTRACT_SNAPSHOT_DEFS", updated_defs_tuple)
    monkeypatch.setattr(run_start_artifacts, "CONTRACT_SNAPSHOT_DEFS", updated_defs_tuple)


async def _assert_run_start_policy_block(
    monkeypatch: pytest.MonkeyPatch,
    *,
    tmp_path: Path,
    epic_id: str,
    artifact_key: str,
    invalid_factory: Any,
    expected_error: str,
) -> None:
    _write_epic_assets(tmp_path, epic_id)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=str(tmp_path / "runtime.db"),
        config_root=tmp_path,
        run_ledger_repo=AsyncProtocolRunLedgerRepository(workspace),
    )
    execute_calls = {"count": 0}

    async def _spy_execute_epic(**_: Any) -> None:
        execute_calls["count"] += 1

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _spy_execute_epic)
    _override_snapshot_factory(monkeypatch, artifact_key=artifact_key, factory=invalid_factory)

    with pytest.raises(ValueError, match=expected_error):
        await pipeline.run_epic(epic_id, build_id=f"build-{epic_id}", session_id=f"sess-{epic_id}")

    assert execute_calls["count"] == 0


@pytest.mark.contract
@pytest.mark.asyncio
async def test_workspace_hygiene_policy_violation_blocks_run_before_model_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Layer: contract. Verifies run-start policy validation fails closed before orchestrator model work."""
    def _invalid_workspace_rules() -> dict[str, Any]:
        payload = workspace_hygiene_rules_snapshot()
        payload["rules"] = []
        _ = validate_workspace_hygiene_rules(payload)
        return payload

    await _assert_run_start_policy_block(
        monkeypatch,
        tmp_path=tmp_path,
        epic_id="workspace-hygiene-policy-block",
        artifact_key="workspace_hygiene_rules",
        invalid_factory=_invalid_workspace_rules,
        expected_error="E_WORKSPACE_HYGIENE_RULES_EMPTY",
    )


@pytest.mark.contract
@pytest.mark.asyncio
async def test_source_attribution_policy_violation_blocks_run_before_model_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Layer: contract. Verifies source-attribution policy validation fails closed before orchestrator model work."""
    def _invalid_source_attribution_policy() -> dict[str, Any]:
        payload = source_attribution_policy_snapshot()
        payload["modes"] = []
        _ = validate_source_attribution_policy(payload)
        return payload

    await _assert_run_start_policy_block(
        monkeypatch,
        tmp_path=tmp_path,
        epic_id="source-attribution-policy-block",
        artifact_key="source_attribution_policy",
        invalid_factory=_invalid_source_attribution_policy,
        expected_error="E_SOURCE_ATTRIBUTION_POLICY_EMPTY",
    )


@pytest.mark.contract
@pytest.mark.asyncio
async def test_trust_language_policy_violation_blocks_run_before_model_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Layer: contract. Verifies trust-language policy validation fails closed before orchestrator model work."""
    def _invalid_trust_language_policy() -> dict[str, Any]:
        payload = trust_language_review_policy_snapshot()
        payload["claims"] = []
        _ = validate_trust_language_review_policy(payload)
        return payload

    await _assert_run_start_policy_block(
        monkeypatch,
        tmp_path=tmp_path,
        epic_id="trust-language-policy-block",
        artifact_key="trust_language_review_policy",
        invalid_factory=_invalid_trust_language_policy,
        expected_error="E_TRUST_LANGUAGE_REVIEW_POLICY_EMPTY",
    )


@pytest.mark.contract
@pytest.mark.asyncio
async def test_unknown_environment_key_blocks_run_before_model_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: contract. Verifies authoritative runtime environment loading fails closed before orchestrator model work."""
    _write_epic_assets(
        tmp_path,
        "environment-config-policy-block",
        environment_payload={
            "name": "standard",
            "model": "test-model",
            "legacy_key": "ignored-before-packet-2",
        },
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=str(tmp_path / "runtime.db"),
        config_root=tmp_path,
        run_ledger_repo=AsyncProtocolRunLedgerRepository(workspace),
    )
    execute_calls = {"count": 0}

    async def _spy_execute_epic(**_: Any) -> None:
        execute_calls["count"] += 1

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _spy_execute_epic)

    with pytest.raises(ValueError, match="E_ENVIRONMENT_CONFIG_UNKNOWN_KEYS:legacy_key"):
        await pipeline.run_epic(
            "environment-config-policy-block",
            build_id="build-environment-config-policy-block",
            session_id="sess-environment-config-policy-block",
        )

    assert execute_calls["count"] == 0


class _NoOpToolbox:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, tool_name: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        del tool_name, args, context
        self.calls += 1
        return {"ok": True}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tool_gate_violation_blocks_before_tool_execution(tmp_path: Path) -> None:
    """Layer: integration. Verifies tool-gate policy rejects out-of-workspace effects before tool execution."""
    dispatcher = ToolDispatcher(
        tool_gate=ToolGate(organization=None, workspace_root=tmp_path),
        middleware=TurnLifecycleInterceptors([]),
        workspace=tmp_path,
        append_memory_event=lambda *args, **kwargs: None,
        hash_payload=lambda payload: "hash",
        load_replay_tool_result=lambda **kwargs: None,
        persist_tool_result=lambda **kwargs: None,
        load_operation_result=lambda **kwargs: None,
        persist_operation_result=lambda **kwargs: None,
        append_protocol_receipt=lambda **kwargs: dict(kwargs.get("receipt") or {}),
        tool_validation_error_factory=lambda violations: RuntimeError(str(violations)),
    )
    toolbox = _NoOpToolbox()
    turn = ExecutionTurn(
        role="coder",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[ToolCall(tool="write_file", args={"path": "../escape.txt", "content": "x"})],
    )

    with pytest.raises(RuntimeError, match="outside workspace"):
        await dispatcher.execute_tools(
            turn=turn,
            toolbox=toolbox,
            context={"roles": ["coder"], "session_id": "sess-tool-gate", "turn_index": 1},
            issue=None,
        )

    assert toolbox.calls == 0


@pytest.mark.integration
def test_nervous_system_flag_violation_blocks_projection_pack(monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: integration. Verifies disabled nervous-system projection pack requests fail closed at the API boundary."""
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.delenv("ORKET_ENABLE_NERVOUS_SYSTEM", raising=False)

    response = client.post(
        "/v1/kernel/projection-pack",
        headers={"X-API-Key": "test-key"},
        json={
            "session_id": "sess-policy-enforcement",
            "trace_id": "trace-policy-enforcement",
            "purpose": "action_path",
            "tool_context_summary": {},
            "policy_context": {},
        },
    )

    assert response.status_code == 400
    assert "disabled" in response.json()["detail"].lower()
