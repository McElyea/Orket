from __future__ import annotations

from orket.runtime.route_decision_artifact import build_route_decision_artifact


class _ExecutionNode:
    pass


class _WiringNode:
    pass


# Layer: unit
def test_build_route_decision_artifact_defaults_to_epic_route() -> None:
    payload = build_route_decision_artifact(
        run_id="run-1",
        workload_kind="epic",
        execution_runtime_node=_ExecutionNode(),
        pipeline_wiring_service=_WiringNode(),
        target_issue_id=None,
        resume_mode=False,
        deterministic_mode_enabled=False,
    )
    assert payload["schema_version"] == "1.0"
    assert payload["route_target"] == "epic"
    assert payload["reason_code"] == "default_epic_route"
    assert payload["deterministic_mode_enabled"] is False


# Layer: contract
def test_build_route_decision_artifact_marks_target_issue_override() -> None:
    payload = build_route_decision_artifact(
        run_id="run-2",
        workload_kind="epic",
        execution_runtime_node=_ExecutionNode(),
        pipeline_wiring_service=_WiringNode(),
        target_issue_id="ISSUE-7",
        resume_mode=False,
        deterministic_mode_enabled=True,
    )
    assert payload["route_target"] == "issue"
    assert payload["target_issue_id"] == "ISSUE-7"
    assert payload["reason_code"] == "target_issue_override"
    assert payload["deterministic_mode_enabled"] is True


# Layer: contract
def test_build_route_decision_artifact_marks_resume_reason() -> None:
    payload = build_route_decision_artifact(
        run_id="run-3",
        workload_kind="epic",
        execution_runtime_node=_ExecutionNode(),
        pipeline_wiring_service=_WiringNode(),
        target_issue_id=None,
        resume_mode=True,
        deterministic_mode_enabled=False,
    )
    assert payload["route_target"] == "epic"
    assert payload["reason_code"] == "resume_stalled_issues"
