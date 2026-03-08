from __future__ import annotations

# Layer: contract

import pytest
from pydantic import ValidationError

from orket_extension_sdk import (
    ControllerChildCall,
    ControllerChildResult,
    ControllerPolicyCaps,
    ControllerRunEnvelope,
    ControllerRunSummary,
)


def test_controller_timeout_values_normalize_to_integer_seconds() -> None:
    child = ControllerChildCall(target_workload="child.alpha", timeout_seconds=3.01)
    caps = ControllerPolicyCaps(child_timeout_seconds=9.0)

    assert child.timeout_seconds == 4
    assert caps.child_timeout_seconds == 9


def test_controller_timeout_validation_is_fail_closed() -> None:
    with pytest.raises(ValidationError, match="controller.child_timeout_invalid"):
        ControllerChildCall(target_workload="child.alpha", timeout_seconds=0)

    with pytest.raises(ValidationError, match="controller.child_timeout_invalid"):
        ControllerPolicyCaps(child_timeout_seconds=float("inf"))


def test_envelope_canonical_json_is_deterministic_for_equivalent_inputs() -> None:
    envelope_one = ControllerRunEnvelope(
        controller_workload_id="controller_workload",
        ancestry=["root"],
        requested_caps=ControllerPolicyCaps(max_depth=1, max_fanout=5, child_timeout_seconds=900),
        children=[
            ControllerChildCall(
                target_workload="child.alpha",
                payload={"beta": 2, "alpha": 1},
                timeout_seconds=10.0,
                metadata={"z": 9, "a": 3},
            ),
            ControllerChildCall(target_workload="child.beta", payload={"x": "y"}),
        ],
    )
    envelope_two = ControllerRunEnvelope(
        controller_workload_id="controller_workload",
        ancestry=["root"],
        requested_caps=ControllerPolicyCaps(max_fanout=5, child_timeout_seconds=900, max_depth=1),
        children=[
            ControllerChildCall(
                target_workload="child.alpha",
                payload={"alpha": 1, "beta": 2},
                timeout_seconds=10,
                metadata={"a": 3, "z": 9},
            ),
            ControllerChildCall(target_workload="child.beta", payload={"x": "y"}),
        ],
    )

    assert envelope_one.canonical_json() == envelope_two.canonical_json()


def test_summary_canonical_json_is_deterministic_for_equivalent_inputs() -> None:
    summary_one = ControllerRunSummary(
        controller_workload_id="controller_workload",
        status="failed",
        requested_caps=ControllerPolicyCaps(max_depth=2, max_fanout=3, child_timeout_seconds=30),
        enforced_caps=ControllerPolicyCaps(max_depth=1, max_fanout=3, child_timeout_seconds=20),
        error_code="controller.child_execution_failed",
        child_results=[
            ControllerChildResult(
                target_workload="child.alpha",
                status="success",
                requested_timeout=30,
                enforced_timeout=20,
                requested_caps=ControllerPolicyCaps(max_depth=2, max_fanout=3, child_timeout_seconds=30),
                enforced_caps=ControllerPolicyCaps(max_depth=1, max_fanout=3, child_timeout_seconds=20),
                artifact_refs=[{"kind": "report", "path": "workspace/a.json"}],
                summary={"b": 2, "a": 1},
            ),
            ControllerChildResult(
                target_workload="child.beta",
                status="failed",
                requested_timeout=30,
                enforced_timeout=20,
                artifact_refs=[],
                normalized_error="controller.child_execution_failed",
                summary={},
            ),
        ],
    )
    summary_two = ControllerRunSummary(
        controller_workload_id="controller_workload",
        status="failed",
        requested_caps=ControllerPolicyCaps(max_fanout=3, max_depth=2, child_timeout_seconds=30),
        enforced_caps=ControllerPolicyCaps(max_fanout=3, max_depth=1, child_timeout_seconds=20),
        error_code="controller.child_execution_failed",
        child_results=[
            ControllerChildResult(
                target_workload="child.alpha",
                status="success",
                requested_timeout=30,
                enforced_timeout=20,
                requested_caps=ControllerPolicyCaps(max_fanout=3, max_depth=2, child_timeout_seconds=30),
                enforced_caps=ControllerPolicyCaps(max_fanout=3, max_depth=1, child_timeout_seconds=20),
                artifact_refs=[{"path": "workspace/a.json", "kind": "report"}],
                summary={"a": 1, "b": 2},
            ),
            ControllerChildResult(
                target_workload="child.beta",
                status="failed",
                requested_timeout=30,
                enforced_timeout=20,
                artifact_refs=[],
                normalized_error="controller.child_execution_failed",
                summary={},
            ),
        ],
    )

    assert summary_one.canonical_json() == summary_two.canonical_json()
    assert summary_one.summary_digest_sha256() == summary_two.summary_digest_sha256()


def test_summary_enforces_result_error_and_blocked_invariants() -> None:
    """Layer: contract."""
    with pytest.raises(ValidationError, match="controller.run_result_invariant_invalid"):
        ControllerRunSummary(controller_workload_id="controller_workload", status="success", error_code="controller.x")

    with pytest.raises(ValidationError, match="controller.run_result_invariant_invalid"):
        ControllerRunSummary(controller_workload_id="controller_workload", status="blocked", error_code=None)

    with pytest.raises(ValidationError, match="controller.run_result_invariant_invalid"):
        ControllerRunSummary(
            controller_workload_id="controller_workload",
            status="blocked",
            error_code="controller.max_depth_exceeded",
            child_results=[ControllerChildResult(target_workload="child.alpha", status="success")],
        )
