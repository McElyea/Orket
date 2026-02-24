from __future__ import annotations

import json

from orket.kernel.v1.validator import compare_runs_v1, replay_run_v1


def test_compare_runs_v1_is_stable_over_100_iterations() -> None:
    request = {
        "contract_version": "kernel_api/v1",
        "run_a": {
            "run_id": "run-a",
            "contract_version": "kernel_api/v1",
            "schema_version": "v1",
            "turn_digests": [
                {
                    "turn_id": "turn-0001",
                    "turn_result_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                }
            ],
            "stage_outcomes": [{"turn_id": "turn-0001", "stage": "promotion", "outcome": "PASS"}],
            "issues": [],
            "events": ["[INFO] [STAGE:promotion] [CODE:I_PROMOTION_PASS] [LOC:/turn-0001] pass |"],
        },
        "run_b": {
            "run_id": "run-b",
            "contract_version": "kernel_api/v1",
            "schema_version": "v1",
            "turn_digests": [
                {
                    "turn_id": "turn-0001",
                    "turn_result_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                }
            ],
            "stage_outcomes": [{"turn_id": "turn-0001", "stage": "promotion", "outcome": "PASS"}],
            "issues": [],
            "events": ["[INFO] [STAGE:promotion] [CODE:I_PROMOTION_PASS] [LOC:/turn-0001] pass |"],
        },
        "compare_mode": "structural_parity",
    }
    baseline = compare_runs_v1(request)
    baseline_json = json.dumps(baseline, sort_keys=True)
    assert baseline["outcome"] == "PASS"
    for _ in range(99):
        current = compare_runs_v1(request)
        assert current["outcome"] == "PASS"
        assert json.dumps(current, sort_keys=True) == baseline_json


def test_replay_run_v1_is_stable_over_100_iterations() -> None:
    request = {
        "contract_version": "kernel_api/v1",
        "run_descriptor": {
            "run_id": "run-replay",
            "workflow_id": "wf-replay",
            "policy_profile_ref": "policy:v1",
            "model_profile_ref": "model:v1",
            "runtime_profile_ref": "runtime:v1",
            "trace_ref": "trace://run-replay",
            "state_ref": "state://run-replay",
            "contract_version": "kernel_api/v1",
            "schema_version": "v1",
        },
    }
    baseline = replay_run_v1(request)
    baseline_json = json.dumps(baseline, sort_keys=True)
    assert baseline["outcome"] == "PASS"
    for _ in range(99):
        current = replay_run_v1(request)
        assert current["outcome"] == "PASS"
        assert json.dumps(current, sort_keys=True) == baseline_json
