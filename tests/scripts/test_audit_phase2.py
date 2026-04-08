# LIFECYCLE: live
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from scripts.audit.audit_support import normalize_json_surface
from scripts.audit.compare_two_runs import build_report as build_compare_report
from scripts.audit.replay_turn import replay_turn_report
from scripts.audit.verify_run_completeness import build_report as build_verify_report


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    _write_text(path, json.dumps(payload, indent=2, ensure_ascii=True) + "\n")


def _runtime_verification_support_payload(*, session_id: str, issue_id: str) -> dict:
    record_path = (
        f"agent_output/verification/runtime_verifier_records/{session_id}/{issue_id.lower()}/"
        "turn_0001_retry_0000.json"
    )
    return {
        "schema_version": "runtime_verification.latest.v2",
        "artifact_role": "support_verification_evidence",
        "artifact_authority": "support_only",
        "authored_output": False,
        "ok": True,
        "overall_evidence_class": "command_execution",
        "evidence_summary": {
            "syntax_only": {
                "evaluated": True,
                "checked_files": ["agent_output/main.py"],
                "commands": [
                    {
                        "command_id": "command:001",
                        "command_display": "python -m compileall -q agent_output",
                        "working_directory": ".",
                        "outcome": "pass",
                        "returncode": 0,
                    }
                ],
            },
            "command_execution": {
                "evaluated": True,
                "commands": [
                    {
                        "command_id": "command:002",
                        "command_display": "python agent_output/main.py",
                        "working_directory": ".",
                        "outcome": "pass",
                        "returncode": 0,
                    }
                ],
            },
            "behavioral_verification": {
                "evaluated": False,
                "stdout_contract_requested": False,
                "json_assertion_count": 0,
                "commands": [],
            },
            "not_evaluated": [
                {
                    "check": "behavioral_verification",
                    "reason": "no runtime stdout contract requested behavioral verification",
                }
            ],
        },
        "checked_files": ["agent_output/main.py"],
        "errors": [],
        "command_results": [
            {
                "command_id": "command:001",
                "command_display": "python -m compileall -q agent_output",
                "working_directory": ".",
                "outcome": "pass",
                "returncode": 0,
                "evidence_class": "syntax_only",
            },
            {
                "command_id": "command:002",
                "command_display": "python agent_output/main.py",
                "working_directory": ".",
                "outcome": "pass",
                "returncode": 0,
                "evidence_class": "command_execution",
            },
        ],
        "failure_breakdown": {},
        "guard_contract": {"result": "pass"},
        "guard_decision": {"action": "continue"},
        "provenance": {
            "run_id": session_id,
            "issue_id": issue_id,
            "turn_index": 1,
            "retry_count": 0,
            "record_id": f"runtime-verification:{session_id}:{issue_id.lower()}:turn:0001:retry:0000",
            "recorded_at": "2026-03-18T12:00:00Z",
        },
        "history": {
            "latest_path": "agent_output/verification/runtime_verification.json",
            "index_path": "agent_output/verification/runtime_verification_index.json",
            "record_path": record_path,
        },
    }


def _build_cards_run(
    workspace: Path,
    *,
    session_id: str,
    issue_id: str,
    output_path: str = "agent_output/main.py",
    output_text: str = "print('ok')\n",
    model_response: str = '{"tool":"write_file","args":{"path":"agent_output/main.py","content":"print(\\"ok\\")"}}',
    include_parsed_tool_calls: bool = True,
    omit_output: bool = False,
) -> None:
    turn_dir = workspace / "observability" / session_id / issue_id / "001_coder"
    _write_json(
        turn_dir / "checkpoint.json",
        {
            "run_id": session_id,
            "issue_id": issue_id,
            "turn_index": 1,
            "role": "coder",
            "model": "qwen2.5-coder:7b",
            "tool_calls": [
                {"tool": "write_file", "args": {"path": output_path, "content": output_text}},
                {"tool": "update_issue_status", "args": {"status": "code_review"}},
            ],
            "prompt_metadata": {
                "prompt_id": "legacy.prompt_compiler",
                "prompt_checksum": f"checksum-{workspace.name}",
            },
        },
    )
    _write_json(
        turn_dir / "messages.json",
        [
            {"role": "system", "content": "Return only JSON tool blocks."},
            {"role": "user", "content": f"Issue {issue_id}: write {output_path} and move to code_review."},
            {
                "role": "user",
                "content": (
                    "Execution Context JSON:\n"
                    + json.dumps(
                        {
                            "issue_id": issue_id,
                            "execution_profile": "builder_guard_app_v1",
                            "artifact_contract": {"primary_output": output_path},
                            "prompt_metadata": {"prompt_checksum": f"checksum-{workspace.name}"},
                        },
                        sort_keys=True,
                    )
                ),
            },
        ],
    )
    _write_text(turn_dir / "model_response.txt", model_response)
    if include_parsed_tool_calls:
        _write_json(
            turn_dir / "parsed_tool_calls.json",
            [{"tool": "write_file", "args": {"path": output_path}}],
        )
    if not omit_output:
        _write_text(workspace / output_path, output_text)
    runtime_verification_payload = _runtime_verification_support_payload(session_id=session_id, issue_id=issue_id)
    _write_json(workspace / "agent_output" / "verification" / "runtime_verification.json", runtime_verification_payload)
    _write_json(
        workspace / runtime_verification_payload["history"]["record_path"],
        runtime_verification_payload,
    )
    _write_json(
        workspace / "agent_output" / "verification" / "runtime_verification_index.json",
        {
            "schema_version": "runtime_verification.index.v1",
            "artifact_role": "support_verification_history_index",
            "artifact_authority": "support_only",
            "authored_output": False,
            "latest_path": "agent_output/verification/runtime_verification.json",
            "latest_record_id": runtime_verification_payload["provenance"]["record_id"],
            "latest_record_path": runtime_verification_payload["history"]["record_path"],
            "index_path": "agent_output/verification/runtime_verification_index.json",
            "history_count": 1,
            "records": [
                {
                    "record_id": runtime_verification_payload["provenance"]["record_id"],
                    "record_path": runtime_verification_payload["history"]["record_path"],
                    "run_id": session_id,
                    "issue_id": issue_id,
                    "turn_index": 1,
                    "retry_count": 0,
                    "seat_name": "code_reviewer",
                    "recorded_at": "2026-03-18T12:00:00Z",
                    "ok": True,
                    "overall_evidence_class": "command_execution",
                }
            ],
        },
    )
    _write_json(
        workspace / "runs" / session_id / "run_summary.json",
        {
            "run_id": session_id,
            "status": "done",
            "tools_used": [],
            "artifact_ids": ["cards_runtime_facts"],
            "failure_reason": None,
            "execution_profile": "builder_guard_app_v1",
            "stop_reason": "completed",
            "artifact_contract": {
                "kind": "app",
                "primary_output": output_path,
                "required_write_paths": [output_path],
            },
            "truthful_runtime_artifact_provenance": {
                "schema_version": "1.0",
                "projection_source": "artifact_provenance_facts",
                "projection_only": True,
                "artifacts": [
                    {
                        "artifact_path": output_path,
                        "issue_id": issue_id,
                        "operation_id": f"op-{workspace.name}",
                        "produced_at": "2026-03-18T12:00:00Z",
                        "source_hash": "hash",
                    }
                ],
            },
            "truthful_runtime_packet2": {
                "projection_source": "packet2_facts",
                "projection_only": True,
                "idempotency": {
                    "surfaces": [
                        {
                            "issue_id": issue_id,
                            "operation_id": f"op-{workspace.name}",
                            "target": f"{issue_id}:code_review",
                        }
                    ]
                }
            },
        },
    )


def _build_odr_run(workspace: Path, *, session_id: str, issue_id: str) -> None:
    odr_artifact_path = f"observability/{session_id}/{issue_id}/odr_refinement.json"
    _write_json(
        workspace / odr_artifact_path,
        {
            "schema_version": "cards.odr.prebuild.v1",
            "run_id": session_id,
            "issue_id": issue_id,
            "history_rounds": [{"round": 1}],
            "odr_stop_reason": "MAX_ROUNDS",
            "odr_valid": True,
            "odr_pending_decisions": 0,
        },
    )
    (workspace / "observability" / session_id / "runtime_contracts").mkdir(parents=True, exist_ok=True)
    _write_json(
        workspace / "runs" / session_id / "run_summary.json",
        {
            "run_id": session_id,
            "status": "terminal_failure",
            "tools_used": [],
            "artifact_ids": ["cards_runtime_facts"],
            "failure_reason": None,
            "execution_profile": "odr_prebuild_builder_guard_v1",
            "stop_reason": "terminal_failure",
            "odr_active": True,
            "odr_artifact_path": odr_artifact_path,
            "odr_stop_reason": "MAX_ROUNDS",
            "odr_valid": True,
            "odr_pending_decisions": 0,
        },
    )


# Layer: contract
@pytest.mark.contract
def test_verify_run_completeness_marks_cards_run_mar_complete(tmp_path: Path) -> None:
    workspace = tmp_path / "cards-complete"
    _build_cards_run(workspace, session_id="run-a", issue_id="ISSUE-A")

    payload = build_verify_report(workspace=workspace, session_id="run-a")

    assert payload["mar_complete"] is True
    assert payload["replay_ready"] is True
    assert payload["stability_status"] == "not_evaluable"
    assert payload["evidence_groups"]["turn_capture"]["turn_count"] == 1


# Layer: contract
@pytest.mark.contract
def test_verify_run_completeness_flags_missing_parsed_tool_calls_when_tool_mode_expected(tmp_path: Path) -> None:
    workspace = tmp_path / "cards-missing-tool-calls"
    _build_cards_run(
        workspace,
        session_id="run-b",
        issue_id="ISSUE-B",
        include_parsed_tool_calls=False,
    )

    payload = build_verify_report(workspace=workspace, session_id="run-b")

    assert payload["mar_complete"] is False
    assert "parsed_tool_calls.json" in " ".join(payload["missing_evidence"])


# Layer: contract
@pytest.mark.contract
def test_verify_run_completeness_rejects_runtime_verification_without_support_semantics(tmp_path: Path) -> None:
    workspace = tmp_path / "cards-weak-verifier"
    _build_cards_run(workspace, session_id="run-c", issue_id="ISSUE-C")

    runtime_path = workspace / "agent_output" / "verification" / "runtime_verification.json"
    payload = json.loads(runtime_path.read_text(encoding="utf-8"))
    payload.pop("artifact_role")
    _write_json(runtime_path, payload)

    report = build_verify_report(workspace=workspace, session_id="run-c")

    assert report["mar_complete"] is False
    assert any("artifact_role" in item for item in report["missing_evidence"])


# Layer: contract
@pytest.mark.contract
def test_verify_run_completeness_accepts_odr_only_run_surface(tmp_path: Path) -> None:
    workspace = tmp_path / "odr-complete"
    _build_odr_run(workspace, session_id="run-odr", issue_id="ODR-ISSUE")

    payload = build_verify_report(workspace=workspace, session_id="run-odr")

    assert payload["mar_complete"] is True
    assert payload["replay_ready"] is True
    assert payload["evidence_groups"]["turn_capture"]["turn_count"] == 0


# Layer: contract
@pytest.mark.contract
def test_verify_run_completeness_rejects_untrusted_run_summary_projection(tmp_path: Path) -> None:
    workspace = tmp_path / "cards-untrusted-summary"
    session_id = "run-untrusted"
    _build_cards_run(workspace, session_id=session_id, issue_id="ISSUE-UNTRUSTED")

    run_summary_path = workspace / "runs" / session_id / "run_summary.json"
    payload = json.loads(run_summary_path.read_text(encoding="utf-8"))
    payload["control_plane"] = {
        "projection_source": "legacy_cards_summary",
        "projection_only": True,
    }
    _write_json(run_summary_path, payload)

    report = build_verify_report(workspace=workspace, session_id=session_id)

    assert report["mar_complete"] is False
    assert "run_summary.invalid_or_untrusted" in report["missing_evidence"]


# Layer: integration
@pytest.mark.integration
def test_compare_two_runs_excludes_fresh_identity_differences(tmp_path: Path) -> None:
    workspace_a = tmp_path / "compare-a"
    workspace_b = tmp_path / "compare-b"
    _build_cards_run(workspace_a, session_id="run-a", issue_id="ISSUE-A")
    _build_cards_run(workspace_b, session_id="run-b", issue_id="ISSUE-B")

    payload = build_compare_report(
        workspace_a=workspace_a,
        session_id_a="run-a",
        workspace_b=workspace_b,
        session_id_b="run-b",
    )

    assert payload["verdict"] == "stable"
    assert payload["first_in_scope_diff"] is None
    assert payload["excluded_fresh_identity_differences"]


# Layer: unit
@pytest.mark.unit
def test_normalize_run_summary_excludes_fresh_control_plane_identity_fields() -> None:
    left = {
        "run_id": "run-a",
        "status": "done",
        "control_plane": {
            "projection_source": "control_plane_records",
            "projection_only": True,
            "run_id": "cards-epic-run:run-a:build-a:20260318T120000Z",
            "attempt_id": "cards-epic-run:run-a:build-a:20260318T120000Z:attempt:0001",
            "current_attempt_id": "cards-epic-run:run-a:build-a:20260318T120000Z:attempt:0001",
            "configuration_snapshot_id": "cards-epic-config:run-a:build-a",
            "policy_snapshot_id": "cards-epic-policy:run-a:build-a",
            "step_id": "cards-epic-step:run-a:build-a",
            "step_receipt_refs": ["cards-epic-receipt:run-a:build-a"],
            "step_resources_touched": ["build:build-a", "epic:probe"],
            "attempt_ordinal": 1,
            "attempt_state": "attempt_completed",
            "run_state": "completed",
        },
    }
    right = {
        "run_id": "run-b",
        "status": "done",
        "control_plane": {
            "projection_source": "control_plane_records",
            "projection_only": True,
            "run_id": "cards-epic-run:run-b:build-b:20260318T120500Z",
            "attempt_id": "cards-epic-run:run-b:build-b:20260318T120500Z:attempt:0001",
            "current_attempt_id": "cards-epic-run:run-b:build-b:20260318T120500Z:attempt:0001",
            "configuration_snapshot_id": "cards-epic-config:run-b:build-b",
            "policy_snapshot_id": "cards-epic-policy:run-b:build-b",
            "step_id": "cards-epic-step:run-b:build-b",
            "step_receipt_refs": ["cards-epic-receipt:run-b:build-b"],
            "step_resources_touched": ["build:build-b", "epic:probe"],
            "attempt_ordinal": 1,
            "attempt_state": "attempt_completed",
            "run_state": "completed",
        },
    }

    assert normalize_json_surface(left, surface_kind="run_summary", replacements=[]) == normalize_json_surface(
        right,
        surface_kind="run_summary",
        replacements=[],
    )


# Layer: integration
@pytest.mark.integration
def test_compare_two_runs_reports_first_governed_diff(tmp_path: Path) -> None:
    workspace_a = tmp_path / "compare-diff-a"
    workspace_b = tmp_path / "compare-diff-b"
    _build_cards_run(workspace_a, session_id="run-a", issue_id="ISSUE-A", output_text="print('a')\n")
    _build_cards_run(workspace_b, session_id="run-b", issue_id="ISSUE-B", output_text="print('b')\n")

    payload = build_compare_report(
        workspace_a=workspace_a,
        session_id_a="run-a",
        workspace_b=workspace_b,
        session_id_b="run-b",
    )

    assert payload["verdict"] == "diverged"
    assert payload["first_in_scope_diff"]["group"] == "authored_output"
    assert payload["first_in_scope_diff"]["path"] == "$"


# Layer: contract
@pytest.mark.contract
def test_compare_two_runs_blocks_when_mar_evidence_missing(tmp_path: Path) -> None:
    workspace_a = tmp_path / "compare-blocked-a"
    workspace_b = tmp_path / "compare-blocked-b"
    _build_cards_run(workspace_a, session_id="run-a", issue_id="ISSUE-A")
    _build_cards_run(workspace_b, session_id="run-b", issue_id="ISSUE-B", omit_output=True)

    payload = build_compare_report(
        workspace_a=workspace_a,
        session_id_a="run-a",
        workspace_b=workspace_b,
        session_id_b="run-b",
    )

    assert payload["verdict"] == "blocked"
    assert payload["evidence_missing"]["run_b"]


def _fake_engine_factory(message: str) -> type:
    class _FakeEngine:
        def __init__(self, _workspace: Path) -> None:
            self.workspace = _workspace

        def replay_turn(self, *, session_id: str, issue_id: str, turn_index: int, role: str | None = None) -> dict[str, object]:
            return {
                "turn_dir": f"{session_id}/{issue_id}/{turn_index}",
                "checkpoint": {
                    "run_id": session_id,
                    "issue_id": issue_id,
                    "turn_index": turn_index,
                    "role": role or "coder",
                    "model": "qwen2.5-coder:7b",
                },
                "messages": [{"role": "user", "content": f"Issue {issue_id}: do the work."}],
                "model_response": message,
                "parsed_tool_calls": [{"tool": "write_file"}],
            }

    return _FakeEngine


# Layer: unit
@pytest.mark.unit
def test_replay_turn_reports_structural_verdict(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    async def _replay_call(*, messages: list[dict[str, str]], model: str, runtime_context: dict[str, object]) -> dict[str, object]:
        assert messages[0]["role"] == "user"
        assert model == "qwen2.5-coder:7b"
        assert runtime_context["turn_index"] == 1
        return {"content": "same-response", "raw": {"provider": "fake"}}

    monkeypatch.setattr("scripts.audit.replay_turn.OrchestrationEngine", _fake_engine_factory("same-response"))

    payload = asyncio.run(
        replay_turn_report(
            workspace=tmp_path,
            session_id="run-a",
            issue_id="ISSUE-A",
            turn_index=1,
            role="coder",
            replay_call=_replay_call,
        )
    )

    assert payload["stability_status"] == "stable"
    assert payload["structural_verdict"]["match"] is True


# Layer: unit
@pytest.mark.unit
def test_replay_turn_reports_blocked_when_provider_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    async def _replay_call(*, messages: list[dict[str, str]], model: str, runtime_context: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("ollama connection refused")

    monkeypatch.setattr("scripts.audit.replay_turn.OrchestrationEngine", _fake_engine_factory("original-response"))

    payload = asyncio.run(
        replay_turn_report(
            workspace=tmp_path,
            session_id="run-a",
            issue_id="ISSUE-A",
            turn_index=1,
            role="coder",
            replay_call=_replay_call,
        )
    )

    assert payload["stability_status"] == "blocked"
    assert payload["observed_result"] == "environment blocker"
