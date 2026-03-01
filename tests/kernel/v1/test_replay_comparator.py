from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from scripts.replay_comparator import compare_payload

CONTRACTS_ROOT = Path("docs/projects/archive/OS-Stale-2026-02-28/contracts")


def _base_payload() -> dict:
    turn = {
        "turn_id": "turn-0001",
        "issues": [
            {
                "contract_version": "kernel_api/v1",
                "level": "FAIL",
                "stage": "capability",
                "code": "E_CAPABILITY_DENIED",
                "location": "/capabilities/decisions_v1_2_1/0",
                "message": "Denied by policy.",
                "details": {"subject": "agent:test"},
            }
        ],
    }
    return {
        "expected": {
            "run_id": "run-a",
            "registry_digest": "a" * 64,
            "digests": {"policy_digest": "b" * 64, "runtime_digest": "c" * 64, "registry_digest": "a" * 64},
            "turn_results": [turn],
        },
        "actual": {
            "run_id": "run-b",
            "registry_digest": "a" * 64,
            "digests": {"policy_digest": "b" * 64, "runtime_digest": "c" * 64, "registry_digest": "a" * 64},
            "turn_results": [deepcopy(turn)],
        },
    }


def test_registry_lock_mismatch_sets_divergent_code() -> None:
    payload = _base_payload()
    payload["actual"]["registry_digest"] = "d" * 64
    report = compare_payload(payload=payload, stage_order_path=str(CONTRACTS_ROOT / "stage-order-v1.json"))
    assert report["status"] == "DIVERGENT"
    assert report["exit_code"] == "E_REGISTRY_DIGEST_MISMATCH"


def test_version_digest_mismatch_sets_version_code() -> None:
    payload = _base_payload()
    payload["actual"]["digests"]["policy_digest"] = "e" * 64
    report = compare_payload(payload=payload, stage_order_path=str(CONTRACTS_ROOT / "stage-order-v1.json"))
    assert report["status"] == "DIVERGENT"
    assert report["exit_code"] == "E_REPLAY_VERSION_MISMATCH"


def test_issue_message_drift_is_safe_boundary() -> None:
    payload = _base_payload()
    payload["actual"]["turn_results"][0]["issues"][0]["message"] = "Different human message."
    report = compare_payload(payload=payload, stage_order_path=str(CONTRACTS_ROOT / "stage-order-v1.json"))
    assert report["status"] == "MATCH"
    assert report["outcome"] == "PASS"
    assert report["mismatches_detail"] == []


def test_issue_key_multiplicity_mismatch_fails_parity() -> None:
    payload = _base_payload()
    payload["actual"]["turn_results"][0]["issues"].append(payload["actual"]["turn_results"][0]["issues"][0].copy())
    report = compare_payload(payload=payload, stage_order_path=str(CONTRACTS_ROOT / "stage-order-v1.json"))
    assert report["status"] == "DIVERGENT"
    assert report["exit_code"] == "E_REPLAY_EQUIVALENCE_FAILED"
    assert any(m["surface"] == "issue" for m in report["mismatches_detail"])


def test_mismatches_are_sorted_deterministically() -> None:
    payload = _base_payload()
    payload["expected"]["turn_results"] = [
        {
            "turn_id": "turn-0002",
            "issues": [
                {
                    "contract_version": "kernel_api/v1",
                    "level": "FAIL",
                    "stage": "replay",
                    "code": "E_REPLAY_EQUIVALENCE_FAILED",
                    "location": "/x",
                    "message": "x",
                    "details": {"k": 1},
                }
            ],
        },
        payload["expected"]["turn_results"][0],
    ]
    payload["actual"]["turn_results"] = [
        payload["actual"]["turn_results"][0],
        {
            "turn_id": "turn-0002",
            "issues": [],
        },
    ]
    report = compare_payload(payload=payload, stage_order_path=str(CONTRACTS_ROOT / "stage-order-v1.json"))
    ordered = report["mismatches_detail"]
    keys = [
        (m["turn_id"], m["stage_index"], m.get("ordinal", 0), m["surface"], m["path"])
        for m in ordered
    ]
    assert keys == sorted(keys)


def test_report_id_nullification_rule_is_stable() -> None:
    payload = _base_payload()
    payload["actual"]["turn_results"][0]["issues"].append(payload["actual"]["turn_results"][0]["issues"][0].copy())
    report_a = compare_payload(payload=payload, stage_order_path=str(CONTRACTS_ROOT / "stage-order-v1.json"))
    report_b = compare_payload(payload=payload, stage_order_path=str(CONTRACTS_ROOT / "stage-order-v1.json"))
    assert report_a["report_id"] == report_b["report_id"]
