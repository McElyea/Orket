from __future__ import annotations

from pathlib import Path
import tempfile

from orket.kernel.v1.validator import execute_turn_v1, finish_run_v1, start_run_v1


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

