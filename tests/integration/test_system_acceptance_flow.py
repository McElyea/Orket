from __future__ import annotations

import json

import pytest

from orket.adapters.llm.local_model_provider import LocalModelProvider, ModelResponse
from orket.core.domain import ReservationStatus
from orket.exceptions import ExecutionFailed
from orket.orchestration.engine import OrchestrationEngine
from orket.schema import CardStatus
from tests.turn_prompt_utils import extract_turn_prompt_context

# Fixture acceptance coverage is intentionally secondary to canonical-asset acceptance flow.
FIXTURE_SECONDARY = True


class AcceptanceProvider:
    def __init__(self, mode: str):
        self.mode = mode

    async def complete(self, messages):
        turn_context = extract_turn_prompt_context(messages)
        active_role = str(turn_context.get("role") or "").strip().lower()
        readable_paths = [
            path
            for path in turn_context.get("required_read_paths", [])
            if path not in set(turn_context.get("missing_required_read_paths", []))
        ]
        if self.mode == "approve":
            if active_role in {"integrity_guard", "verifier_seat"}:
                read_calls = [
                    f'```json\n{json.dumps({"tool": "read_file", "args": {"path": path}})}\n```'
                    for path in readable_paths
                ]
                return ModelResponse(
                    content="\n".join(
                        read_calls + ['```json\n{"tool": "update_issue_status", "args": {"status": "done"}}\n```']
                    ),
                    raw={"model": "dummy", "total_tokens": 50},
                )
            return ModelResponse(
                content='```json\n{"tool": "write_file", "args": {"path": "agent_output/acceptance.txt", "content": "ok"}}\n```\n```json\n{"tool": "update_issue_status", "args": {"status": "code_review"}}\n```',
                raw={"model": "dummy", "total_tokens": 80},
            )

        if self.mode == "reject":
            if active_role in {"integrity_guard", "verifier_seat"}:
                read_calls = [
                    f'```json\n{json.dumps({"tool": "read_file", "args": {"path": path}})}\n```'
                    for path in readable_paths
                ]
                return ModelResponse(
                    content="\n".join(
                        read_calls
                        + [
                            '{"rationale":"Insufficient acceptance criteria coverage.","violations":["missing acceptance criteria"],"remediation_actions":["Document explicit acceptance criteria before merge."]}',
                            '```json\n{"tool": "update_issue_status", "args": {"status": "blocked", "wait_reason": "review"}}\n```',
                        ]
                    ),
                    raw={"model": "dummy", "total_tokens": 50},
                )
            return ModelResponse(
                content='```json\n{"tool": "write_file", "args": {"path": "agent_output/acceptance.txt", "content": "ok"}}\n```\n```json\n{"tool": "update_issue_status", "args": {"status": "code_review"}}\n```',
                raw={"model": "dummy", "total_tokens": 80},
            )

        # Illegal state transition path: coder attempts direct READY -> DONE.
        return ModelResponse(
            content='```json\n{"tool": "update_issue_status", "args": {"status": "done"}}\n```',
            raw={"model": "dummy", "total_tokens": 40},
        )


class ToolApprovalContinuationProvider:
    async def complete(self, messages):
        turn_context = extract_turn_prompt_context(messages)
        active_role = str(turn_context.get("role") or "").strip().lower()
        current_status = str(turn_context.get("current_status") or "").strip().lower()
        if current_status == "code_review" or active_role in {"reviewer_seat", "code_reviewer"}:
            return ModelResponse(
                content='```json\n{"tool": "update_issue_status", "args": {"status": "done"}}\n```',
                raw={"model": "dummy", "total_tokens": 40},
            )
        return ModelResponse(
            content='```json\n{"tool": "write_file", "args": {"path": "agent_output/approved.txt", "content": "approved"}}\n```\n```json\n{"tool": "update_issue_status", "args": {"status": "code_review"}}\n```',
            raw={"model": "dummy", "total_tokens": 80},
        )


class RawJsonProvider:
    async def complete(self, messages):
        turn_context = extract_turn_prompt_context(messages)
        active_role = str(turn_context.get("role") or "").strip().lower()
        current_status = str(turn_context.get("current_status") or "").strip().lower()
        if current_status == "code_review" or active_role in {"reviewer_seat", "code_reviewer"}:
            return ModelResponse(
                content='{"tool": "update_issue_status", "args": {"status": "done"}}',
                raw={"model": "dummy", "total_tokens": 40},
            )
        return ModelResponse(
            content=(
                '{"tool": "write_file", "args": {"path": "agent_output/raw.txt", "content": "ok"}}\n'
                '{"tool": "update_issue_status", "args": {"status": "code_review"}}'
            ),
            raw={"model": "dummy", "total_tokens": 80},
        )


def _build_assets(root, *, with_guard: bool, epic_id: str):
    (root / "config").mkdir()
    for d in ["epics", "roles", "dialects", "teams", "environments"]:
        (root / "model" / "core" / d).mkdir(parents=True, exist_ok=True)

    (root / "config" / "organization.json").write_text(
        json.dumps(
            {
                "name": "Acceptance Org",
                "vision": "Test",
                "ethos": "Test",
                "branding": {"design_dos": []},
                "architecture": {"cicd_rules": [], "preferred_stack": {}, "idesign_threshold": 7},
                "process_rules": {"small_project_builder_variant": "architect"},
                "departments": ["core"],
            }
        ),
        encoding="utf-8",
    )

    for d_name in ["qwen", "llama3", "deepseek-r1", "phi", "generic"]:
        (root / "model" / "core" / "dialects" / f"{d_name}.json").write_text(
            json.dumps({"model_family": d_name, "dsl_format": "JSON", "constraints": [], "hallucination_guard": "None"}),
            encoding="utf-8",
        )

    (root / "model" / "core" / "roles" / "lead_architect.json").write_text(
        json.dumps(
            {
                "id": "ARCH",
                "summary": "lead_architect",
                "type": "utility",
                "description": "Architect",
                "tools": ["write_file", "update_issue_status"],
            }
        ),
        encoding="utf-8",
    )
    (root / "model" / "core" / "roles" / "integrity_guard.json").write_text(
        json.dumps(
            {
                "id": "VERI",
                "summary": "integrity_guard",
                "type": "utility",
                "description": "Verifier",
                "tools": ["update_issue_status", "read_file"],
            }
        ),
        encoding="utf-8",
    )
    (root / "model" / "core" / "roles" / "code_reviewer.json").write_text(
        json.dumps(
            {
                "id": "REV",
                "summary": "code_reviewer",
                "type": "utility",
                "description": "Reviewer",
                "tools": ["update_issue_status", "read_file"],
            }
        ),
        encoding="utf-8",
    )

    seats = {"lead_architect": {"name": "Lead", "roles": ["lead_architect"]}}
    seats["reviewer_seat"] = {"name": "Reviewer", "roles": ["code_reviewer"]}
    if with_guard:
        seats["verifier_seat"] = {"name": "Verifier", "roles": ["integrity_guard"]}
    (root / "model" / "core" / "teams" / "standard.json").write_text(
        json.dumps({"name": "standard", "seats": seats}),
        encoding="utf-8",
    )
    (root / "model" / "core" / "environments" / "standard.json").write_text(
        json.dumps({"name": "standard", "model": "dummy", "temperature": 0.1, "timeout": 300}),
        encoding="utf-8",
    )

    (root / "model" / "core" / "epics" / f"{epic_id}.json").write_text(
        json.dumps(
            {
                "id": epic_id,
                "name": "System Acceptance Epic",
                "type": "epic",
                "team": "standard",
                "environment": "standard",
                "description": "Acceptance-level flow test",
                "architecture_governance": {"idesign": False, "pattern": "Tactical"},
                "issues": [{"id": "ISSUE-A", "summary": "Run acceptance flow", "seat": "lead_architect", "priority": "High"}],
            }
        ),
        encoding="utf-8",
    )


def _patch_provider(monkeypatch, provider):
    def mock_init(self, *args, **kwargs):
        self.model = "dummy"
        self.timeout = 300

    monkeypatch.setattr(LocalModelProvider, "__init__", mock_init)
    monkeypatch.setattr(LocalModelProvider, "complete", provider.complete)


@pytest.mark.asyncio
async def test_system_acceptance_guard_approves_actions(tmp_path, monkeypatch):
    root = tmp_path
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "agent_output").mkdir()
    (workspace / "verification").mkdir()
    db_path = str(root / "acceptance_approve.db")

    _build_assets(root, with_guard=True, epic_id="acceptance_approve")
    _patch_provider(monkeypatch, AcceptanceProvider(mode="approve"))
    monkeypatch.setenv("ORKET_DISABLE_RUNTIME_VERIFIER", "true")

    engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
    await engine.run_card("acceptance_approve")

    issue = await engine.cards.get_by_id("ISSUE-A")
    assert issue.status == CardStatus.DONE
    assert (workspace / "agent_output" / "acceptance.txt").exists()
    log_blob = (workspace / "orket.log").read_text(encoding="utf-8")
    assert '"event": "guard_approved"' in log_blob
    assert '"event": "guard_review_payload"' in log_blob


@pytest.mark.asyncio
async def test_system_acceptance_guard_rejects_actions(tmp_path, monkeypatch):
    root = tmp_path
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "agent_output").mkdir()
    (workspace / "verification").mkdir()
    db_path = str(root / "acceptance_reject.db")

    _build_assets(root, with_guard=True, epic_id="acceptance_reject")
    _patch_provider(monkeypatch, AcceptanceProvider(mode="reject"))
    monkeypatch.setenv("ORKET_DISABLE_RUNTIME_VERIFIER", "true")

    engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
    await engine.run_card("acceptance_reject")

    issue = await engine.cards.get_by_id("ISSUE-A")
    assert issue.status == CardStatus.BLOCKED
    log_blob = (workspace / "orket.log").read_text(encoding="utf-8")
    assert '"event": "guard_rejected"' in log_blob
    assert '"event": "guard_payload_invalid"' not in log_blob


@pytest.mark.asyncio
async def test_system_acceptance_guard_blocks_illegal_transition(tmp_path, monkeypatch):
    root = tmp_path
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "agent_output").mkdir()
    (workspace / "verification").mkdir()
    db_path = str(root / "acceptance_block.db")

    _build_assets(root, with_guard=False, epic_id="acceptance_block")
    _patch_provider(monkeypatch, AcceptanceProvider(mode="block"))
    monkeypatch.setenv("ORKET_DISABLE_RUNTIME_VERIFIER", "true")

    engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
    with pytest.raises(ExecutionFailed):
        await engine.run_card("acceptance_block")

    issue = await engine.cards.get_by_id("ISSUE-A")
    assert issue.status == CardStatus.BLOCKED
    assert (workspace / "agent_output" / "policy_violation_ISSUE-A.json").exists()


@pytest.mark.asyncio
async def test_system_acceptance_tool_approval_continues_same_governed_run(tmp_path, monkeypatch):
    """Layer: integration."""
    root = tmp_path
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "agent_output").mkdir()
    (workspace / "verification").mkdir()
    durable_root = root / ".orket" / "durable"
    db_path = str(durable_root / "db" / "orket_persistence.db")

    _build_assets(root, with_guard=False, epic_id="approval_required")
    _patch_provider(monkeypatch, ToolApprovalContinuationProvider())
    monkeypatch.setenv("ORKET_DISABLE_RUNTIME_VERIFIER", "true")
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    monkeypatch.setenv("ORKET_DURABLE_ROOT", str(durable_root))

    engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
    loop_policy = engine._pipeline.orchestrator.loop_policy_node

    def _approval_required_tools_for_seat(seat_name, issue=None, turn_status=None):
        if str(seat_name or "").strip().lower() == "lead_architect":
            return ["write_file"]
        return []

    monkeypatch.setattr(loop_policy, "approval_required_tools_for_seat", _approval_required_tools_for_seat)

    with pytest.raises(ExecutionFailed, match="Approval required for tool 'write_file'"):
        await engine.run_card("approval_required")

    issue = await engine.cards.get_by_id("ISSUE-A")
    assert issue.status == CardStatus.IN_PROGRESS

    approvals = await engine.list_approvals(status="PENDING", limit=10)
    assert len(approvals) == 1
    approval = approvals[0]
    run_id = str(approval["control_plane_target_ref"])

    pending_run = await engine.control_plane_execution_repository.get_run_record(run_id=run_id)
    pending_truth = await engine.control_plane_repository.get_final_truth(run_id=run_id)
    resource = await engine.control_plane_repository.get_latest_resource_record(resource_id="namespace:issue:ISSUE-A")

    assert pending_run is not None
    assert pending_run.lifecycle_state.value == "executing"
    assert pending_truth is None
    assert resource is not None
    assert resource.resource_kind == "turn_tool_namespace"

    resolved = await engine.decide_approval(approval_id=str(approval["approval_id"]), decision="approve")

    completed_run = await engine.control_plane_execution_repository.get_run_record(run_id=run_id)
    final_truth = await engine.control_plane_repository.get_final_truth(run_id=run_id)
    reservation = await engine.control_plane_repository.get_latest_reservation_record(
        reservation_id=f"approval-reservation:{approval['approval_id']}"
    )
    issue = await engine.cards.get_by_id("ISSUE-A")

    assert resolved["status"] == "resolved"
    assert resolved["approval"]["status"] == "APPROVED"
    assert completed_run is not None
    assert completed_run.lifecycle_state.value == "completed"
    assert final_truth is not None
    assert final_truth.result_class.value == "success"
    assert reservation is not None
    assert reservation.status is ReservationStatus.RELEASED
    assert issue.status == CardStatus.DONE
    assert (workspace / "agent_output" / "approved.txt").read_text(encoding="utf-8") == "approved"


@pytest.mark.asyncio
async def test_system_acceptance_raw_json_tool_calls_complete_flow(tmp_path, monkeypatch):
    """Layer: integration."""
    root = tmp_path
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "agent_output").mkdir()
    (workspace / "verification").mkdir()
    db_path = str(root / "acceptance_raw_json.db")

    _build_assets(root, with_guard=False, epic_id="acceptance_raw_json")
    _patch_provider(monkeypatch, RawJsonProvider())
    monkeypatch.setenv("ORKET_DISABLE_RUNTIME_VERIFIER", "true")
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")

    engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
    await engine.run_card("acceptance_raw_json")

    issue = await engine.cards.get_by_id("ISSUE-A")
    assert issue.status == CardStatus.DONE
    assert (workspace / "agent_output" / "raw.txt").read_text(encoding="utf-8") == "ok"

