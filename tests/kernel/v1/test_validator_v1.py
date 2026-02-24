from __future__ import annotations

from pathlib import Path
import tempfile

from orket.kernel.v1.validator import (
    authorize_tool_call_v1,
    compare_runs_v1,
    execute_turn_v1,
    finish_run_v1,
    replay_run_v1,
    resolve_capability_v1,
    start_run_v1,
)


def test_start_run_v1_returns_run_handle_shape() -> None:
    response = start_run_v1(
        {
            "contract_version": "kernel_api/v1",
            "workflow_id": "wf-1",
            "visibility_mode": "local_only",
            "workspace_root": ".tmp_kernel",
        }
    )
    assert response["contract_version"] == "kernel_api/v1"
    handle = response["run_handle"]
    assert handle["contract_version"] == "kernel_api/v1"
    assert isinstance(handle["run_id"], str) and handle["run_id"].startswith("run-")
    assert handle["visibility_mode"] == "local_only"


def test_execute_turn_v1_missing_run_id_fails_with_base_shape_code() -> None:
    result = execute_turn_v1(
        {
            "contract_version": "kernel_api/v1",
            "run_handle": {"contract_version": "kernel_api/v1", "visibility_mode": "local_only"},
            "turn_id": "turn-0001",
            "turn_input": {},
        }
    )
    assert result["outcome"] == "FAIL"
    assert result["stage"] == "base_shape"
    codes = [issue["code"] for issue in result["issues"]]
    assert "E_BASE_SHAPE_MISSING_RUN_ID" in codes


def test_execute_turn_v1_stage_and_promote_path_returns_promotion_stage() -> None:
    with tempfile.TemporaryDirectory(prefix="orket_validator_v1_") as tmp:
        result = execute_turn_v1(
            {
                "contract_version": "kernel_api/v1",
                "run_handle": {
                    "contract_version": "kernel_api/v1",
                    "run_id": "run-3000",
                    "visibility_mode": "local_only",
                    "workspace_root": str(Path(tmp)),
                },
                "turn_id": "turn-0001",
                "commit_intent": "stage_and_request_promotion",
                "turn_input": {
                    "stage_triplet": {
                        "stem": "data/dto/v/validator",
                        "body": {"dto_type": "invocation", "id": "inv:validator"},
                        "links": {"declares": {"type": "skill", "id": "skill:validator", "relationship": "declares"}},
                        "manifest": {},
                    }
                },
            }
        )
        assert result["outcome"] == "PASS"
        assert result["stage"] == "promotion"
        assert isinstance(result["events"], list) and result["events"]


def test_finish_run_v1_returns_schema_shape() -> None:
    response = finish_run_v1(
        {
            "contract_version": "kernel_api/v1",
            "run_handle": {
                "contract_version": "kernel_api/v1",
                "run_id": "run-9999",
                "visibility_mode": "local_only",
            },
            "outcome": "PASS",
        }
    )
    assert response == {
        "contract_version": "kernel_api/v1",
        "run_id": "run-9999",
        "outcome": "PASS",
        "turns_executed": 0,
        "events": [],
    }


def test_execute_turn_v1_capability_unresolved_fails_with_capability_stage_code() -> None:
    result = execute_turn_v1(
        {
            "contract_version": "kernel_api/v1",
            "run_handle": {"contract_version": "kernel_api/v1", "run_id": "run-cap", "visibility_mode": "local_only"},
            "turn_id": "turn-0001",
            "turn_input": {
                "context": {"capability_enforcement": True, "capability_resolved": False, "subject": "agent:one"},
                "tool_call": {"action": "tool.call", "resource": "tool://shell"},
            },
        }
    )
    assert result["outcome"] == "FAIL"
    assert result["stage"] == "capability"
    assert any(issue["code"] == "E_CAPABILITY_NOT_RESOLVED" for issue in result["issues"])
    assert result["capabilities"]["mode"] == "enabled"
    assert result["capabilities"]["denied_count"] == 1


def test_execute_turn_v1_capability_module_off_emits_skipped_info() -> None:
    result = execute_turn_v1(
        {
            "contract_version": "kernel_api/v1",
            "run_handle": {"contract_version": "kernel_api/v1", "run_id": "run-cap-off", "visibility_mode": "local_only"},
            "turn_id": "turn-0001",
            "turn_input": {
                "context": {"capability_enforcement": False, "subject": "agent:one"},
                "tool_call": {"action": "tool.call", "resource": "tool://shell"},
            },
        }
    )
    assert result["outcome"] == "PASS"
    assert result["capabilities"]["mode"] == "disabled"
    assert any("I_CAPABILITY_SKIPPED" in event for event in result["events"])


def test_execute_turn_v1_capability_can_grant_from_policy_permissions() -> None:
    result = execute_turn_v1(
        {
            "contract_version": "kernel_api/v1",
            "run_handle": {"contract_version": "kernel_api/v1", "run_id": "run-cap-grant", "visibility_mode": "local_only"},
            "turn_id": "turn-0001",
            "turn_input": {
                "context": {"capability_enforcement": True, "role": "coder", "task": "edit", "subject": "agent:one"},
                "tool_call": {"action": "tool.call", "resource": "tool://shell"},
            },
        }
    )
    assert result["outcome"] == "PASS"
    assert result["stage"] == "capability"
    assert result["capabilities"]["granted_count"] == 1
    assert result["capabilities"]["decisions"][0]["evidence"]["capability_source"] == "model/core/contracts/kernel_capability_policy_v1.json"


def test_authorize_tool_call_v1_is_deny_by_default() -> None:
    response = authorize_tool_call_v1(
        {
            "contract_version": "kernel_api/v1",
            "context": {"subject": "agent:one", "capability_enforcement": True},
            "tool_request": {"action": "tool.call", "resource": "tool://shell"},
        }
    )
    decision = response["decision"]
    assert decision["result"] == "DENY"
    assert decision["reason_code"] == "E_CAPABILITY_DENIED"


def test_authorize_tool_call_v1_allow_includes_policy_source_and_version_metadata() -> None:
    response = authorize_tool_call_v1(
        {
            "contract_version": "kernel_api/v1",
            "context": {
                "subject": "agent:one",
                "capability_enforcement": True,
                "allow_tool_call": True,
                "policy_source": "policy://kernel/v1/capability",
                "policy_version": "2026-02-24",
            },
            "tool_request": {"action": "tool.call", "resource": "tool://shell"},
        }
    )
    decision = response["decision"]
    assert decision["result"] == "GRANT"
    assert decision["reason_code"] == "I_GATEKEEPER_PASS"
    assert decision["evidence"]["capability_source"] == "policy://kernel/v1/capability"
    assert decision["evidence"]["capability_version"] == "2026-02-24"


def test_resolve_capability_v1_module_off_returns_skipped_event() -> None:
    response = resolve_capability_v1(
        {
            "contract_version": "kernel_api/v1",
            "role": "coder",
            "task": "edit",
            "context": {"capability_enforcement": False},
        }
    )
    assert response["capability_plan"]["mode"] == "disabled"
    assert any("I_CAPABILITY_SKIPPED" in event for event in response["events"])


def test_resolve_capability_v1_reads_permissions_from_policy_artifact() -> None:
    response = resolve_capability_v1(
        {
            "contract_version": "kernel_api/v1",
            "role": "coder",
            "task": "edit",
            "context": {"capability_enforcement": True},
        }
    )
    plan = response["capability_plan"]
    assert plan["mode"] == "enabled"
    assert plan["permissions"] == ["file.read", "file.write", "tool.call"]
    assert plan["policy_source"] == "model/core/contracts/kernel_capability_policy_v1.json"
    assert plan["policy_version"] == "2026-02-24"


def test_authorize_tool_call_v1_can_grant_from_policy_permissions() -> None:
    response = authorize_tool_call_v1(
        {
            "contract_version": "kernel_api/v1",
            "context": {"subject": "agent:one", "role": "coder", "task": "edit", "capability_enforcement": True},
            "tool_request": {"action": "tool.call", "resource": "tool://shell"},
        }
    )
    decision = response["decision"]
    assert decision["result"] == "GRANT"
    assert decision["reason_code"] == "I_GATEKEEPER_PASS"
    assert decision["evidence"]["capability_source"] == "model/core/contracts/kernel_capability_policy_v1.json"


def test_replay_run_v1_missing_input_emits_missing_code() -> None:
    report = replay_run_v1({"contract_version": "kernel_api/v1", "run_descriptor": {"run_id": "run-r1"}})
    assert report["outcome"] == "FAIL"
    assert any(issue["code"] == "E_REPLAY_INPUT_MISSING" for issue in report["issues"])


def test_replay_run_v1_version_mismatch_emits_version_code() -> None:
    report = replay_run_v1(
        {
            "contract_version": "kernel_api/v1",
            "run_descriptor": {
                "run_id": "run-r2",
                "workflow_id": "wf-r2",
                "policy_profile_ref": "policy:v1",
                "model_profile_ref": "model:v1",
                "runtime_profile_ref": "runtime:v1",
                "trace_ref": "trace://run-r2",
                "state_ref": "state://run-r2",
                "contract_version": "kernel_api/v0",
                "schema_version": "v1",
            },
        }
    )
    assert report["outcome"] == "FAIL"
    assert any(issue["code"] == "E_REPLAY_VERSION_MISMATCH" for issue in report["issues"])


def test_compare_runs_v1_mismatch_emits_equivalence_failed() -> None:
    report = compare_runs_v1(
        {
            "contract_version": "kernel_api/v1",
            "run_a": {"run_id": "run-a", "turn_digests": [{"turn_id": "turn-0001", "turn_result_digest": "0" * 64}]},
            "run_b": {"run_id": "run-b", "turn_digests": [{"turn_id": "turn-0001", "turn_result_digest": "1" * 64}]},
            "compare_mode": "structural_parity",
        }
    )
    assert report["outcome"] == "FAIL"
    assert any(issue["code"] == "E_REPLAY_EQUIVALENCE_FAILED" for issue in report["issues"])
