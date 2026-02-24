from __future__ import annotations

from copy import deepcopy

from orket.kernel.v1.canonical import compute_turn_result_digest
from orket.kernel.v1.validator import execute_turn_v1


def _sample_turn_result() -> dict:
    return execute_turn_v1(
        {
            "contract_version": "kernel_api/v1",
            "run_handle": {"contract_version": "kernel_api/v1", "run_id": "run-digest", "visibility_mode": "local_only"},
            "turn_id": "turn-0001",
            "turn_input": {
                "context": {"capability_enforcement": True, "subject": "agent:one"},
                "tool_call": {"action": "tool.call", "resource": "tool://shell"},
            },
        }
    )


def test_events_do_not_change_turn_result_digest() -> None:
    base = _sample_turn_result()
    changed = deepcopy(base)
    changed["events"] = changed.get("events", []) + ["[INFO] [STAGE:replay] [CODE:I_FIXTURE_MODE] [LOC:/x] noise |"]
    assert compute_turn_result_digest(base) == compute_turn_result_digest(changed)


def test_issue_message_does_not_change_turn_result_digest() -> None:
    base = _sample_turn_result()
    changed = deepcopy(base)
    if changed.get("issues"):
        changed["issues"][0]["message"] = "different diagnostic text"
    assert compute_turn_result_digest(base) == compute_turn_result_digest(changed)


def test_structural_change_changes_turn_result_digest() -> None:
    base = _sample_turn_result()
    changed = deepcopy(base)
    changed["stage"] = "replay"
    assert compute_turn_result_digest(base) != compute_turn_result_digest(changed)
