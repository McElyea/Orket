from __future__ import annotations

import pytest

import orket.runtime.run_summary as run_summary_module
from orket.runtime.run_summary import build_run_summary_payload, validate_run_summary_payload

_STARTED_AT = "2036-03-05T12:00:00+00:00"
_FINALIZED_AT = "2036-03-05T12:00:05+00:00"


def _run_identity(*, run_id: str) -> dict[str, object]:
    return {
        "run_id": run_id,
        "workload": "summary-projection-validation",
        "start_time": _STARTED_AT,
        "identity_scope": "session_bootstrap",
        "projection_source": "session_bootstrap_artifacts",
        "projection_only": True,
    }


def _payload_with_extension(*, extension_artifacts: dict) -> dict:
    return build_run_summary_payload(
        run_id="sess-summary-projection-validation",
        status="done",
        failure_reason=None,
        started_at=_STARTED_AT,
        ended_at=_FINALIZED_AT,
        tool_names=["workspace.read"],
        artifacts={
            "run_identity": _run_identity(run_id="sess-summary-projection-validation"),
            **extension_artifacts,
        },
    )


@pytest.mark.parametrize(
    ("payload_key", "extension_artifacts", "expected_error"),
    [
        (
            "control_plane",
            {
                "control_plane_run_record": {
                    "contract_version": "control_plane.contract.v1",
                    "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                    "workload_id": "cards-epic",
                    "workload_version": "1.0",
                    "policy_snapshot_id": "policy-1",
                    "policy_digest": "sha256:policy-1",
                    "configuration_snapshot_id": "config-1",
                    "configuration_digest": "sha256:config-1",
                    "creation_timestamp": _STARTED_AT,
                    "admission_decision_receipt_ref": "admission-1",
                    "lifecycle_state": "waiting_on_observation",
                    "current_attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                },
                "control_plane_attempt_record": {
                    "contract_version": "control_plane.contract.v1",
                    "attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                    "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                    "attempt_ordinal": 1,
                    "attempt_state": "attempt_waiting",
                    "starting_state_snapshot_ref": "admission-1",
                    "start_timestamp": _STARTED_AT,
                }
            },
            "run_summary_control_plane_projection_source_invalid",
        ),
        (
            "truthful_runtime_packet1",
            {
                "packet1_facts": {
                    "primary_artifact_output": {"id": "agent_output/runtime_verification.json", "kind": "artifact"},
                }
            },
            "run_summary_truthful_runtime_packet1_projection_source_invalid",
        ),
        (
            "truthful_runtime_packet2",
            {
                "packet2_facts": {
                    "repair_entries": [
                        {
                            "repair_id": "repair:ISSUE-1:1:corrective_reprompt",
                            "turn_index": 1,
                            "source_event": "turn_corrective_reprompt",
                            "strategy": "corrective_reprompt",
                            "reasons": ["consistency_scope_contract_not_met"],
                            "material_change": True,
                        }
                    ],
                    "final_disposition": "accepted_with_repair",
                }
            },
            "run_summary_truthful_runtime_packet2_projection_source_invalid",
        ),
        (
            "truthful_runtime_artifact_provenance",
            {
                "artifact_provenance_facts": {
                    "artifacts": [
                        {
                            "artifact_path": "agent_output/main.py",
                            "artifact_type": "source_code",
                            "generator": "tool.write_file",
                            "generator_version": "1.0.0",
                            "source_hash": "a" * 64,
                            "produced_at": "2036-03-05T12:00:03+00:00",
                            "truth_classification": "direct",
                        }
                    ]
                }
            },
            "run_summary_truthful_runtime_artifact_provenance_projection_source_invalid",
        ),
    ],
)
def test_run_summary_rejects_projection_blocks_with_wrong_source(
    payload_key: str,
    extension_artifacts: dict,
    expected_error: str,
) -> None:
    payload = _payload_with_extension(
        extension_artifacts=extension_artifacts,
    )
    payload[payload_key]["projection_source"] = "wrong_source"

    with pytest.raises(ValueError, match=expected_error):
        validate_run_summary_payload(payload)


@pytest.mark.parametrize(
    ("payload_key", "extension_artifacts", "expected_error"),
    [
        (
            "control_plane",
            {
                "control_plane_run_record": {
                    "contract_version": "control_plane.contract.v1",
                    "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                    "workload_id": "cards-epic",
                    "workload_version": "1.0",
                    "policy_snapshot_id": "policy-1",
                    "policy_digest": "sha256:policy-1",
                    "configuration_snapshot_id": "config-1",
                    "configuration_digest": "sha256:config-1",
                    "creation_timestamp": _STARTED_AT,
                    "admission_decision_receipt_ref": "admission-1",
                    "lifecycle_state": "waiting_on_observation",
                    "current_attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                },
                "control_plane_attempt_record": {
                    "contract_version": "control_plane.contract.v1",
                    "attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                    "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                    "attempt_ordinal": 1,
                    "attempt_state": "attempt_waiting",
                    "starting_state_snapshot_ref": "admission-1",
                    "start_timestamp": _STARTED_AT,
                }
            },
            "run_summary_control_plane_projection_only_invalid",
        ),
        (
            "truthful_runtime_packet1",
            {
                "packet1_facts": {
                    "primary_artifact_output": {"id": "agent_output/runtime_verification.json", "kind": "artifact"},
                }
            },
            "run_summary_truthful_runtime_packet1_projection_only_invalid",
        ),
        (
            "truthful_runtime_packet2",
            {
                "packet2_facts": {
                    "repair_entries": [
                        {
                            "repair_id": "repair:ISSUE-1:1:corrective_reprompt",
                            "turn_index": 1,
                            "source_event": "turn_corrective_reprompt",
                            "strategy": "corrective_reprompt",
                            "reasons": ["consistency_scope_contract_not_met"],
                            "material_change": True,
                        }
                    ],
                    "final_disposition": "accepted_with_repair",
                }
            },
            "run_summary_truthful_runtime_packet2_projection_only_invalid",
        ),
        (
            "truthful_runtime_artifact_provenance",
            {
                "artifact_provenance_facts": {
                    "artifacts": [
                        {
                            "artifact_path": "agent_output/main.py",
                            "artifact_type": "source_code",
                            "generator": "tool.write_file",
                            "generator_version": "1.0.0",
                            "source_hash": "a" * 64,
                            "produced_at": "2036-03-05T12:00:03+00:00",
                            "truth_classification": "direct",
                        }
                    ]
                }
            },
            "run_summary_truthful_runtime_artifact_provenance_projection_only_invalid",
        ),
    ],
)
def test_run_summary_rejects_projection_blocks_without_projection_only(
    payload_key: str,
    extension_artifacts: dict,
    expected_error: str,
) -> None:
    payload = _payload_with_extension(
        extension_artifacts=extension_artifacts,
    )
    payload[payload_key]["projection_only"] = False

    with pytest.raises(ValueError, match=expected_error):
        validate_run_summary_payload(payload)


@pytest.mark.parametrize(
    ("field_name", "field_value", "expected_error"),
    [
        ("identity_scope", "invocation_scope", "run_summary_run_identity_identity_scope_invalid"),
        ("projection_source", "legacy_bootstrap", "run_summary_run_identity_projection_source_invalid"),
        ("projection_only", False, "run_summary_run_identity_projection_only_invalid"),
    ],
)
def test_run_summary_rejects_run_identity_projection_drift(
    field_name: str,
    field_value: object,
    expected_error: str,
) -> None:
    payload = _payload_with_extension(extension_artifacts={})
    payload["run_identity"] = _run_identity(run_id="sess-summary-projection-validation")
    payload["run_identity"][field_name] = field_value

    with pytest.raises(ValueError, match=expected_error):
        build_run_summary_payload(
            run_id="sess-summary-projection-validation",
            status="done",
            failure_reason=None,
            started_at=_STARTED_AT,
            ended_at=_FINALIZED_AT,
            tool_names=["workspace.read"],
            artifacts={"run_identity": payload["run_identity"]},
        )


@pytest.mark.parametrize(
    ("field_name", "field_value", "expected_error"),
    [
        ("identity_scope", "invocation_scope", "run_summary_run_identity_identity_scope_invalid"),
        ("projection_source", "legacy_bootstrap", "run_summary_run_identity_projection_source_invalid"),
        ("projection_only", False, "run_summary_run_identity_projection_only_invalid"),
    ],
)
def test_validate_run_summary_payload_rejects_run_identity_projection_drift(
    field_name: str,
    field_value: object,
    expected_error: str,
) -> None:
    payload = _payload_with_extension(extension_artifacts={})
    payload["run_identity"] = _run_identity(run_id="sess-summary-projection-validation")
    payload["run_identity"][field_name] = field_value

    with pytest.raises(ValueError, match=expected_error):
        validate_run_summary_payload(payload)


def test_validate_run_summary_payload_rejects_run_identity_run_id_mismatch() -> None:
    """Layer: contract. Verifies summary payload validation fail-closes if bootstrap run identity drifts."""
    payload = _payload_with_extension(extension_artifacts={})
    payload["run_identity"] = _run_identity(run_id="sess-summary-other")

    with pytest.raises(ValueError, match="run_summary_run_identity_run_id_mismatch"):
        validate_run_summary_payload(payload)


def test_build_run_summary_payload_rejects_run_identity_run_id_mismatch() -> None:
    """Layer: contract. Verifies summary building fail-closes if bootstrap run identity drifts."""
    with pytest.raises(ValueError, match="run_summary_run_identity_run_id_mismatch"):
        build_run_summary_payload(
            run_id="sess-summary-projection-validation",
            status="done",
            failure_reason=None,
            started_at=_STARTED_AT,
            ended_at=_FINALIZED_AT,
            tool_names=["workspace.read"],
            artifacts={"run_identity": _run_identity(run_id="sess-summary-other")},
        )


def test_validate_run_summary_payload_rejects_control_plane_attempt_alignment_drift() -> None:
    """Layer: contract. Verifies summary payload validation fail-closes if control-plane attempt projection drifts."""
    payload = _payload_with_extension(
        extension_artifacts={
            "control_plane_run_record": {
                "contract_version": "control_plane.contract.v1",
                "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                "workload_id": "cards-epic",
                "workload_version": "1.0",
                "policy_snapshot_id": "policy-1",
                "policy_digest": "sha256:policy-1",
                "configuration_snapshot_id": "config-1",
                "configuration_digest": "sha256:config-1",
                "creation_timestamp": _STARTED_AT,
                "admission_decision_receipt_ref": "admission-1",
                "lifecycle_state": "waiting_on_observation",
                "current_attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
            },
            "control_plane_attempt_record": {
                "contract_version": "control_plane.contract.v1",
                "attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                "attempt_ordinal": 1,
                "attempt_state": "attempt_waiting",
                "starting_state_snapshot_ref": "admission-1",
                "start_timestamp": _STARTED_AT,
            },
        }
    )
    payload["control_plane"]["current_attempt_id"] = (
        "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:9999"
    )

    with pytest.raises(ValueError, match="run_summary_control_plane_current_attempt_id_mismatch"):
        validate_run_summary_payload(payload)


def test_build_run_summary_payload_rejects_control_plane_attempt_alignment_drift() -> None:
    """Layer: contract. Verifies summary building fail-closes if control-plane attempt projection drifts."""
    with pytest.raises(ValueError, match="run_summary_control_plane_current_attempt_id_mismatch"):
        build_run_summary_payload(
            run_id="sess-summary-projection-validation",
            status="done",
            failure_reason=None,
            started_at=_STARTED_AT,
            ended_at=_FINALIZED_AT,
            tool_names=["workspace.read"],
            artifacts={
                "run_identity": _run_identity(run_id="sess-summary-projection-validation"),
                "control_plane_run_record": {
                    "contract_version": "control_plane.contract.v1",
                    "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                    "workload_id": "cards-epic",
                    "workload_version": "1.0",
                    "policy_snapshot_id": "policy-1",
                    "policy_digest": "sha256:policy-1",
                    "configuration_snapshot_id": "config-1",
                    "configuration_digest": "sha256:config-1",
                    "creation_timestamp": _STARTED_AT,
                    "admission_decision_receipt_ref": "admission-1",
                    "lifecycle_state": "waiting_on_observation",
                    "current_attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:9999",
                },
                "control_plane_attempt_record": {
                    "contract_version": "control_plane.contract.v1",
                    "attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                    "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                    "attempt_ordinal": 1,
                    "attempt_state": "attempt_waiting",
                    "starting_state_snapshot_ref": "admission-1",
                    "start_timestamp": _STARTED_AT,
                },
            },
        )


def test_validate_run_summary_payload_rejects_control_plane_attempt_run_lineage_drift() -> None:
    """Layer: contract. Verifies summary payload validation fail-closes if attempt lineage drifts from the projected run."""
    payload = _payload_with_extension(
        extension_artifacts={
            "control_plane_run_record": {
                "contract_version": "control_plane.contract.v1",
                "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                "workload_id": "cards-epic",
                "workload_version": "1.0",
                "policy_snapshot_id": "policy-1",
                "policy_digest": "sha256:policy-1",
                "configuration_snapshot_id": "config-1",
                "configuration_digest": "sha256:config-1",
                "creation_timestamp": _STARTED_AT,
                "admission_decision_receipt_ref": "admission-1",
                "lifecycle_state": "waiting_on_observation",
                "current_attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
            },
            "control_plane_attempt_record": {
                "contract_version": "control_plane.contract.v1",
                "attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                "attempt_ordinal": 1,
                "attempt_state": "attempt_waiting",
                "starting_state_snapshot_ref": "admission-1",
                "start_timestamp": _STARTED_AT,
            },
        }
    )
    payload["control_plane"]["attempt_id"] = (
        "cards-epic-run:sess-summary-other:build-1:20360305T120000000000Z:attempt:0001"
    )

    with pytest.raises(ValueError, match="run_summary_control_plane_attempt_id_run_lineage_mismatch"):
        validate_run_summary_payload(payload)


def test_build_run_summary_payload_rejects_control_plane_attempt_run_lineage_drift() -> None:
    """Layer: contract. Verifies summary building fail-closes if attempt lineage drifts from the projected run."""
    with pytest.raises(ValueError, match="run_summary_control_plane_attempt_id_run_lineage_mismatch"):
        build_run_summary_payload(
            run_id="sess-summary-projection-validation",
            status="done",
            failure_reason=None,
            started_at=_STARTED_AT,
            ended_at=_FINALIZED_AT,
            tool_names=["workspace.read"],
            artifacts={
                "run_identity": _run_identity(run_id="sess-summary-projection-validation"),
                "control_plane_run_record": {
                    "contract_version": "control_plane.contract.v1",
                    "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                    "workload_id": "cards-epic",
                    "workload_version": "1.0",
                    "policy_snapshot_id": "policy-1",
                    "policy_digest": "sha256:policy-1",
                    "configuration_snapshot_id": "config-1",
                    "configuration_digest": "sha256:config-1",
                    "creation_timestamp": _STARTED_AT,
                    "admission_decision_receipt_ref": "admission-1",
                    "lifecycle_state": "waiting_on_observation",
                    "current_attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                },
                "control_plane_attempt_record": {
                    "contract_version": "control_plane.contract.v1",
                    "attempt_id": "cards-epic-run:sess-summary-other:build-1:20360305T120000000000Z:attempt:0001",
                    "run_id": "cards-epic-run:sess-summary-other:build-1:20360305T120000000000Z",
                    "attempt_ordinal": 1,
                    "attempt_state": "attempt_waiting",
                    "starting_state_snapshot_ref": "admission-1",
                    "start_timestamp": _STARTED_AT,
                },
            },
        )


def test_validate_run_summary_payload_rejects_control_plane_step_run_lineage_drift() -> None:
    """Layer: contract. Verifies summary payload validation fail-closes if step lineage drifts from the projected run."""
    payload = _payload_with_extension(
        extension_artifacts={
            "control_plane_run_record": {
                "contract_version": "control_plane.contract.v1",
                "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                "workload_id": "cards-epic",
                "workload_version": "1.0",
                "policy_snapshot_id": "policy-1",
                "policy_digest": "sha256:policy-1",
                "configuration_snapshot_id": "config-1",
                "configuration_digest": "sha256:config-1",
                "creation_timestamp": _STARTED_AT,
                "admission_decision_receipt_ref": "admission-1",
                "lifecycle_state": "waiting_on_observation",
                "current_attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
            },
            "control_plane_attempt_record": {
                "contract_version": "control_plane.contract.v1",
                "attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                "attempt_ordinal": 1,
                "attempt_state": "attempt_waiting",
                "starting_state_snapshot_ref": "admission-1",
                "start_timestamp": _STARTED_AT,
            },
            "control_plane_step_record": {
                "contract_version": "control_plane.contract.v1",
                "step_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:step:start",
                "attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                "step_kind": "cards_epic_session_start",
                "input_ref": "admission-1",
                "output_ref": "admission-1",
                "capability_used": "deterministic_compute",
                "resources_touched": ["epic:summary-projection-validation"],
                "observed_result_classification": "cards_epic_run_started",
                "receipt_refs": ["admission-1"],
                "closure_classification": "step_completed",
            },
        }
    )
    payload["control_plane"]["step_id"] = "cards-epic-run:sess-summary-other:build-1:20360305T120000000000Z:step:start"

    with pytest.raises(ValueError, match="run_summary_control_plane_step_id_run_lineage_mismatch"):
        validate_run_summary_payload(payload)


def test_build_run_summary_payload_rejects_control_plane_step_run_lineage_drift() -> None:
    """Layer: contract. Verifies summary building fail-closes if step lineage drifts from the projected run."""
    with pytest.raises(ValueError, match="run_summary_control_plane_step_id_run_lineage_mismatch"):
        build_run_summary_payload(
            run_id="sess-summary-projection-validation",
            status="done",
            failure_reason=None,
            started_at=_STARTED_AT,
            ended_at=_FINALIZED_AT,
            tool_names=["workspace.read"],
            artifacts={
                "run_identity": _run_identity(run_id="sess-summary-projection-validation"),
                "control_plane_run_record": {
                    "contract_version": "control_plane.contract.v1",
                    "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                    "workload_id": "cards-epic",
                    "workload_version": "1.0",
                    "policy_snapshot_id": "policy-1",
                    "policy_digest": "sha256:policy-1",
                    "configuration_snapshot_id": "config-1",
                    "configuration_digest": "sha256:config-1",
                    "creation_timestamp": _STARTED_AT,
                    "admission_decision_receipt_ref": "admission-1",
                    "lifecycle_state": "waiting_on_observation",
                    "current_attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                },
                "control_plane_attempt_record": {
                    "contract_version": "control_plane.contract.v1",
                    "attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                    "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                    "attempt_ordinal": 1,
                    "attempt_state": "attempt_waiting",
                    "starting_state_snapshot_ref": "admission-1",
                    "start_timestamp": _STARTED_AT,
                },
                "control_plane_step_record": {
                    "contract_version": "control_plane.contract.v1",
                    "step_id": "cards-epic-run:sess-summary-other:build-1:20360305T120000000000Z:step:start",
                    "attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                    "step_kind": "cards_epic_session_start",
                    "input_ref": "admission-1",
                    "output_ref": "admission-1",
                    "capability_used": "deterministic_compute",
                    "resources_touched": ["epic:summary-projection-validation"],
                    "observed_result_classification": "cards_epic_run_started",
                    "receipt_refs": ["admission-1"],
                    "closure_classification": "step_completed",
                },
            },
        )


def test_validate_run_summary_payload_rejects_control_plane_run_projection_omission() -> None:
    """Layer: contract. Verifies summary payload validation fail-closes if a run projection drops core run fields."""
    payload = _payload_with_extension(
        extension_artifacts={
            "control_plane_run_record": {
                "contract_version": "control_plane.contract.v1",
                "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                "workload_id": "cards-epic",
                "workload_version": "1.0",
                "policy_snapshot_id": "policy-1",
                "policy_digest": "sha256:policy-1",
                "configuration_snapshot_id": "config-1",
                "configuration_digest": "sha256:config-1",
                "creation_timestamp": _STARTED_AT,
                "admission_decision_receipt_ref": "admission-1",
                "lifecycle_state": "waiting_on_observation",
                "current_attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
            },
            "control_plane_attempt_record": {
                "contract_version": "control_plane.contract.v1",
                "attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                "attempt_ordinal": 1,
                "attempt_state": "attempt_waiting",
                "starting_state_snapshot_ref": "admission-1",
                "start_timestamp": _STARTED_AT,
            },
        }
    )
    payload["control_plane"].pop("workload_id", None)

    with pytest.raises(ValueError, match="run_summary_control_plane_workload_id_required"):
        validate_run_summary_payload(payload)


@pytest.mark.parametrize(
    ("missing_field", "expected_error"),
    [
        ("run_id", "run_summary_control_plane_run_id_required"),
        ("attempt_id", "run_summary_control_plane_attempt_id_required"),
    ],
)
def test_validate_run_summary_payload_rejects_control_plane_identity_hierarchy_omission(
    missing_field: str,
    expected_error: str,
) -> None:
    """Layer: contract. Verifies summary payload validation fail-closes if lower-level control-plane ids survive without their parent ids."""
    payload = _payload_with_extension(
        extension_artifacts={
            "control_plane_run_record": {
                "contract_version": "control_plane.contract.v1",
                "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                "workload_id": "cards-epic",
                "workload_version": "1.0",
                "policy_snapshot_id": "policy-1",
                "policy_digest": "sha256:policy-1",
                "configuration_snapshot_id": "config-1",
                "configuration_digest": "sha256:config-1",
                "creation_timestamp": _STARTED_AT,
                "admission_decision_receipt_ref": "admission-1",
                "lifecycle_state": "waiting_on_observation",
                "current_attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
            },
            "control_plane_attempt_record": {
                "contract_version": "control_plane.contract.v1",
                "attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                "attempt_ordinal": 1,
                "attempt_state": "attempt_waiting",
                "starting_state_snapshot_ref": "admission-1",
                "start_timestamp": _STARTED_AT,
            },
            "control_plane_step_record": {
                "contract_version": "control_plane.contract.v1",
                "step_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:step:start",
                "attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                "step_kind": "cards_epic_session_start",
                "input_ref": "admission-1",
                "output_ref": "admission-1",
                "capability_used": "deterministic_compute",
                "resources_touched": ["epic:summary-projection-validation"],
                "observed_result_classification": "cards_epic_run_started",
                "receipt_refs": ["admission-1"],
                "closure_classification": "step_completed",
            },
        }
    )
    payload["control_plane"].pop(missing_field, None)

    with pytest.raises(ValueError, match=expected_error):
        validate_run_summary_payload(payload)


def test_validate_run_summary_payload_rejects_orphaned_current_attempt_projection() -> None:
    """Layer: contract. Verifies summary payload validation fails closed if current_attempt_id survives after attempt_id and step_id drop."""
    payload = _payload_with_extension(
        extension_artifacts={
            "control_plane_run_record": {
                "contract_version": "control_plane.contract.v1",
                "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                "workload_id": "cards-epic",
                "workload_version": "1.0",
                "policy_snapshot_id": "policy-1",
                "policy_digest": "sha256:policy-1",
                "configuration_snapshot_id": "config-1",
                "configuration_digest": "sha256:config-1",
                "creation_timestamp": _STARTED_AT,
                "admission_decision_receipt_ref": "admission-1",
                "lifecycle_state": "waiting_on_observation",
                "current_attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
            },
            "control_plane_attempt_record": {
                "contract_version": "control_plane.contract.v1",
                "attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                "attempt_ordinal": 1,
                "attempt_state": "attempt_waiting",
                "starting_state_snapshot_ref": "admission-1",
                "start_timestamp": _STARTED_AT,
            },
        }
    )
    payload["control_plane"].pop("attempt_id", None)
    payload["control_plane"].pop("step_id", None)
    payload["control_plane"].pop("step_kind", None)
    payload["control_plane"].pop("attempt_state", None)
    payload["control_plane"].pop("attempt_ordinal", None)

    with pytest.raises(ValueError, match="run_summary_control_plane_attempt_id_required"):
        validate_run_summary_payload(payload)


@pytest.mark.parametrize(
    ("orphaned_field", "expected_error"),
    [
        ("attempt_state", "run_summary_control_plane_attempt_id_required"),
        ("attempt_ordinal", "run_summary_control_plane_attempt_id_required"),
        ("step_kind", "run_summary_control_plane_step_id_required"),
    ],
)
def test_validate_run_summary_payload_rejects_orphaned_control_plane_projection_metadata(
    orphaned_field: str,
    expected_error: str,
) -> None:
    """Layer: contract. Verifies summary payload validation fails closed if attempt or step metadata survives after its projected id drops."""
    payload = _payload_with_extension(
        extension_artifacts={
            "control_plane_run_record": {
                "contract_version": "control_plane.contract.v1",
                "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                "workload_id": "cards-epic",
                "workload_version": "1.0",
                "policy_snapshot_id": "policy-1",
                "policy_digest": "sha256:policy-1",
                "configuration_snapshot_id": "config-1",
                "configuration_digest": "sha256:config-1",
                "creation_timestamp": _STARTED_AT,
                "admission_decision_receipt_ref": "admission-1",
                "lifecycle_state": "waiting_on_observation",
                "current_attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
            },
            "control_plane_attempt_record": {
                "contract_version": "control_plane.contract.v1",
                "attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                "attempt_ordinal": 1,
                "attempt_state": "attempt_waiting",
                "starting_state_snapshot_ref": "admission-1",
                "start_timestamp": _STARTED_AT,
            },
            "control_plane_step_record": {
                "contract_version": "control_plane.contract.v1",
                "step_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:step:start",
                "attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                "step_kind": "cards_epic_session_start",
                "input_ref": "admission-1",
                "output_ref": "admission-1",
                "capability_used": "deterministic_compute",
                "resources_touched": ["epic:summary-projection-validation"],
                "observed_result_classification": "cards_epic_run_started",
                "receipt_refs": ["admission-1"],
                "closure_classification": "step_completed",
            },
        }
    )
    if orphaned_field == "attempt_state":
        payload["control_plane"].pop("current_attempt_id", None)
        payload["control_plane"].pop("attempt_id", None)
        payload["control_plane"].pop("attempt_ordinal", None)
        payload["control_plane"].pop("step_id", None)
        payload["control_plane"].pop("step_kind", None)
    elif orphaned_field == "attempt_ordinal":
        payload["control_plane"].pop("current_attempt_id", None)
        payload["control_plane"].pop("attempt_id", None)
        payload["control_plane"].pop("attempt_state", None)
        payload["control_plane"].pop("step_id", None)
        payload["control_plane"].pop("step_kind", None)
    else:
        payload["control_plane"].pop("step_id", None)

    with pytest.raises(ValueError, match=expected_error):
        validate_run_summary_payload(payload)


@pytest.mark.parametrize(
    ("field_name", "field_value", "expected_error"),
    [
        ("attempt_state", "", "run_summary_control_plane_attempt_state_required"),
        ("attempt_ordinal", None, "run_summary_control_plane_attempt_ordinal_required"),
        ("step_kind", "", "run_summary_control_plane_step_kind_required"),
    ],
)
def test_validate_run_summary_payload_rejects_control_plane_attempt_or_step_projection_omission(
    field_name: str,
    field_value: object,
    expected_error: str,
) -> None:
    """Layer: contract. Verifies summary payload validation fail-closes if attempt/step projection metadata is dropped."""
    payload = _payload_with_extension(
        extension_artifacts={
            "control_plane_run_record": {
                "contract_version": "control_plane.contract.v1",
                "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                "workload_id": "cards-epic",
                "workload_version": "1.0",
                "policy_snapshot_id": "policy-1",
                "policy_digest": "sha256:policy-1",
                "configuration_snapshot_id": "config-1",
                "configuration_digest": "sha256:config-1",
                "creation_timestamp": _STARTED_AT,
                "admission_decision_receipt_ref": "admission-1",
                "lifecycle_state": "waiting_on_observation",
                "current_attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
            },
            "control_plane_attempt_record": {
                "contract_version": "control_plane.contract.v1",
                "attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                "attempt_ordinal": 1,
                "attempt_state": "attempt_waiting",
                "starting_state_snapshot_ref": "admission-1",
                "start_timestamp": _STARTED_AT,
            },
            "control_plane_step_record": {
                "contract_version": "control_plane.contract.v1",
                "step_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:step:start",
                "attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                "step_kind": "cards_epic_session_start",
                "input_ref": "admission-1",
                "output_ref": "admission-1",
                "capability_used": "deterministic_compute",
                "resources_touched": ["epic:summary-projection-validation"],
                "observed_result_classification": "cards_epic_run_started",
                "receipt_refs": ["admission-1"],
                "closure_classification": "step_completed",
            },
        }
    )
    payload["control_plane"][field_name] = field_value

    with pytest.raises(ValueError, match=expected_error):
        validate_run_summary_payload(payload)


def test_build_run_summary_payload_rejects_control_plane_run_projection_omission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Layer: contract. Verifies summary building fail-closes if a run projection drops core run fields."""
    original_build_control_plane = run_summary_module.build_control_plane_summary_projection

    def _projection_without_workload_id(*, artifacts):  # type: ignore[no-untyped-def]
        projection = original_build_control_plane(artifacts=artifacts)
        assert projection is not None
        projection.pop("workload_id", None)
        return projection

    monkeypatch.setattr(
        run_summary_module,
        "build_control_plane_summary_projection",
        _projection_without_workload_id,
    )

    with pytest.raises(ValueError, match="run_summary_control_plane_workload_id_required"):
        build_run_summary_payload(
            run_id="sess-summary-projection-validation",
            status="done",
            failure_reason=None,
            started_at=_STARTED_AT,
            ended_at=_FINALIZED_AT,
            tool_names=["workspace.read"],
            artifacts={
                "run_identity": _run_identity(run_id="sess-summary-projection-validation"),
                "control_plane_run_record": {
                    "contract_version": "control_plane.contract.v1",
                    "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                    "workload_id": "cards-epic",
                    "workload_version": "1.0",
                    "policy_snapshot_id": "policy-1",
                    "policy_digest": "sha256:policy-1",
                    "configuration_snapshot_id": "config-1",
                    "configuration_digest": "sha256:config-1",
                    "creation_timestamp": _STARTED_AT,
                    "admission_decision_receipt_ref": "admission-1",
                    "lifecycle_state": "waiting_on_observation",
                    "current_attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                },
                "control_plane_attempt_record": {
                    "contract_version": "control_plane.contract.v1",
                    "attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                    "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                    "attempt_ordinal": 1,
                    "attempt_state": "attempt_waiting",
                    "starting_state_snapshot_ref": "admission-1",
                    "start_timestamp": _STARTED_AT,
                },
            },
        )


@pytest.mark.parametrize(
    ("missing_field", "expected_error"),
    [
        ("run_id", "run_summary_control_plane_run_id_required"),
        ("attempt_id", "run_summary_control_plane_attempt_id_required"),
    ],
)
def test_build_run_summary_payload_rejects_control_plane_identity_hierarchy_omission(
    monkeypatch: pytest.MonkeyPatch,
    missing_field: str,
    expected_error: str,
) -> None:
    """Layer: contract. Verifies summary building fail-closes if lower-level control-plane ids survive without their parent ids."""
    original_build_control_plane = run_summary_module.build_control_plane_summary_projection

    def _projection_without_required_identity(*, artifacts):  # type: ignore[no-untyped-def]
        projection = original_build_control_plane(artifacts=artifacts)
        assert projection is not None
        projection.pop(missing_field, None)
        return projection

    monkeypatch.setattr(
        run_summary_module,
        "build_control_plane_summary_projection",
        _projection_without_required_identity,
    )

    with pytest.raises(ValueError, match=expected_error):
        build_run_summary_payload(
            run_id="sess-summary-projection-validation",
            status="done",
            failure_reason=None,
            started_at=_STARTED_AT,
            ended_at=_FINALIZED_AT,
            tool_names=["workspace.read"],
            artifacts={
                "run_identity": _run_identity(run_id="sess-summary-projection-validation"),
                "control_plane_run_record": {
                    "contract_version": "control_plane.contract.v1",
                    "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                    "workload_id": "cards-epic",
                    "workload_version": "1.0",
                    "policy_snapshot_id": "policy-1",
                    "policy_digest": "sha256:policy-1",
                    "configuration_snapshot_id": "config-1",
                    "configuration_digest": "sha256:config-1",
                    "creation_timestamp": _STARTED_AT,
                    "admission_decision_receipt_ref": "admission-1",
                    "lifecycle_state": "waiting_on_observation",
                    "current_attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                },
                "control_plane_attempt_record": {
                    "contract_version": "control_plane.contract.v1",
                    "attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                    "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                    "attempt_ordinal": 1,
                    "attempt_state": "attempt_waiting",
                    "starting_state_snapshot_ref": "admission-1",
                    "start_timestamp": _STARTED_AT,
                },
                "control_plane_step_record": {
                    "contract_version": "control_plane.contract.v1",
                    "step_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:step:start",
                    "attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                    "step_kind": "cards_epic_session_start",
                    "input_ref": "admission-1",
                    "output_ref": "admission-1",
                    "capability_used": "deterministic_compute",
                    "resources_touched": ["epic:summary-projection-validation"],
                    "observed_result_classification": "cards_epic_run_started",
                    "receipt_refs": ["admission-1"],
                    "closure_classification": "step_completed",
                },
            },
        )


def test_build_run_summary_payload_rejects_orphaned_current_attempt_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Layer: contract. Verifies summary building fails closed if current_attempt_id survives after attempt_id and step_id drop."""
    original_build_control_plane = run_summary_module.build_control_plane_summary_projection

    def _projection_without_attempt_identity(*, artifacts):  # type: ignore[no-untyped-def]
        projection = original_build_control_plane(artifacts=artifacts)
        assert projection is not None
        projection.pop("attempt_id", None)
        projection.pop("step_id", None)
        projection.pop("step_kind", None)
        projection.pop("attempt_state", None)
        projection.pop("attempt_ordinal", None)
        return projection

    monkeypatch.setattr(
        run_summary_module,
        "build_control_plane_summary_projection",
        _projection_without_attempt_identity,
    )

    with pytest.raises(ValueError, match="run_summary_control_plane_attempt_id_required"):
        build_run_summary_payload(
            run_id="sess-summary-projection-validation",
            status="done",
            failure_reason=None,
            started_at=_STARTED_AT,
            ended_at=_FINALIZED_AT,
            tool_names=["workspace.read"],
            artifacts={
                "run_identity": _run_identity(run_id="sess-summary-projection-validation"),
                "control_plane_run_record": {
                    "contract_version": "control_plane.contract.v1",
                    "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                    "workload_id": "cards-epic",
                    "workload_version": "1.0",
                    "policy_snapshot_id": "policy-1",
                    "policy_digest": "sha256:policy-1",
                    "configuration_snapshot_id": "config-1",
                    "configuration_digest": "sha256:config-1",
                    "creation_timestamp": _STARTED_AT,
                    "admission_decision_receipt_ref": "admission-1",
                    "lifecycle_state": "waiting_on_observation",
                    "current_attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                },
                "control_plane_attempt_record": {
                    "contract_version": "control_plane.contract.v1",
                    "attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                    "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                    "attempt_ordinal": 1,
                    "attempt_state": "attempt_waiting",
                    "starting_state_snapshot_ref": "admission-1",
                    "start_timestamp": _STARTED_AT,
                },
            },
        )


@pytest.mark.parametrize(
    ("orphaned_field", "expected_error"),
    [
        ("attempt_state", "run_summary_control_plane_attempt_id_required"),
        ("attempt_ordinal", "run_summary_control_plane_attempt_id_required"),
        ("step_kind", "run_summary_control_plane_step_id_required"),
    ],
)
def test_build_run_summary_payload_rejects_orphaned_control_plane_projection_metadata(
    monkeypatch: pytest.MonkeyPatch,
    orphaned_field: str,
    expected_error: str,
) -> None:
    """Layer: contract. Verifies summary building fails closed if attempt or step metadata survives after its projected id drops."""
    original_build_control_plane = run_summary_module.build_control_plane_summary_projection

    def _projection_with_orphaned_metadata(*, artifacts):  # type: ignore[no-untyped-def]
        projection = original_build_control_plane(artifacts=artifacts)
        assert projection is not None
        if orphaned_field == "attempt_state":
            projection.pop("current_attempt_id", None)
            projection.pop("attempt_id", None)
            projection.pop("attempt_ordinal", None)
            projection.pop("step_id", None)
            projection.pop("step_kind", None)
        elif orphaned_field == "attempt_ordinal":
            projection.pop("current_attempt_id", None)
            projection.pop("attempt_id", None)
            projection.pop("attempt_state", None)
            projection.pop("step_id", None)
            projection.pop("step_kind", None)
        else:
            projection.pop("step_id", None)
        return projection

    monkeypatch.setattr(
        run_summary_module,
        "build_control_plane_summary_projection",
        _projection_with_orphaned_metadata,
    )

    with pytest.raises(ValueError, match=expected_error):
        build_run_summary_payload(
            run_id="sess-summary-projection-validation",
            status="done",
            failure_reason=None,
            started_at=_STARTED_AT,
            ended_at=_FINALIZED_AT,
            tool_names=["workspace.read"],
            artifacts={
                "run_identity": _run_identity(run_id="sess-summary-projection-validation"),
                "control_plane_run_record": {
                    "contract_version": "control_plane.contract.v1",
                    "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                    "workload_id": "cards-epic",
                    "workload_version": "1.0",
                    "policy_snapshot_id": "policy-1",
                    "policy_digest": "sha256:policy-1",
                    "configuration_snapshot_id": "config-1",
                    "configuration_digest": "sha256:config-1",
                    "creation_timestamp": _STARTED_AT,
                    "admission_decision_receipt_ref": "admission-1",
                    "lifecycle_state": "waiting_on_observation",
                    "current_attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                },
                "control_plane_attempt_record": {
                    "contract_version": "control_plane.contract.v1",
                    "attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                    "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                    "attempt_ordinal": 1,
                    "attempt_state": "attempt_waiting",
                    "starting_state_snapshot_ref": "admission-1",
                    "start_timestamp": _STARTED_AT,
                },
                "control_plane_step_record": {
                    "contract_version": "control_plane.contract.v1",
                    "step_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:step:start",
                    "attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                    "step_kind": "cards_epic_session_start",
                    "input_ref": "admission-1",
                    "output_ref": "admission-1",
                    "capability_used": "deterministic_compute",
                    "resources_touched": ["epic:summary-projection-validation"],
                    "observed_result_classification": "cards_epic_run_started",
                    "receipt_refs": ["admission-1"],
                    "closure_classification": "step_completed",
                },
            },
        )


@pytest.mark.parametrize(
    ("field_name", "expected_error"),
    [
        ("attempt_state", "run_summary_control_plane_attempt_state_required"),
        ("attempt_ordinal", "run_summary_control_plane_attempt_ordinal_required"),
        ("step_kind", "run_summary_control_plane_step_kind_required"),
    ],
)
def test_build_run_summary_payload_rejects_control_plane_attempt_or_step_projection_omission(
    monkeypatch: pytest.MonkeyPatch,
    field_name: str,
    expected_error: str,
) -> None:
    """Layer: contract. Verifies summary building fail-closes if attempt/step projection metadata is dropped."""
    original_build_control_plane = run_summary_module.build_control_plane_summary_projection

    def _projection_without_required_field(*, artifacts):  # type: ignore[no-untyped-def]
        projection = original_build_control_plane(artifacts=artifacts)
        assert projection is not None
        projection.pop(field_name, None)
        return projection

    monkeypatch.setattr(
        run_summary_module,
        "build_control_plane_summary_projection",
        _projection_without_required_field,
    )

    with pytest.raises(ValueError, match=expected_error):
        build_run_summary_payload(
            run_id="sess-summary-projection-validation",
            status="done",
            failure_reason=None,
            started_at=_STARTED_AT,
            ended_at=_FINALIZED_AT,
            tool_names=["workspace.read"],
            artifacts={
                "run_identity": _run_identity(run_id="sess-summary-projection-validation"),
                "control_plane_run_record": {
                    "contract_version": "control_plane.contract.v1",
                    "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                    "workload_id": "cards-epic",
                    "workload_version": "1.0",
                    "policy_snapshot_id": "policy-1",
                    "policy_digest": "sha256:policy-1",
                    "configuration_snapshot_id": "config-1",
                    "configuration_digest": "sha256:config-1",
                    "creation_timestamp": _STARTED_AT,
                    "admission_decision_receipt_ref": "admission-1",
                    "lifecycle_state": "waiting_on_observation",
                    "current_attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                },
                "control_plane_attempt_record": {
                    "contract_version": "control_plane.contract.v1",
                    "attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                    "run_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z",
                    "attempt_ordinal": 1,
                    "attempt_state": "attempt_waiting",
                    "starting_state_snapshot_ref": "admission-1",
                    "start_timestamp": _STARTED_AT,
                },
                "control_plane_step_record": {
                    "contract_version": "control_plane.contract.v1",
                    "step_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:step:start",
                    "attempt_id": "cards-epic-run:sess-summary-projection-validation:build-1:20360305T120000000000Z:attempt:0001",
                    "step_kind": "cards_epic_session_start",
                    "input_ref": "admission-1",
                    "output_ref": "admission-1",
                    "capability_used": "deterministic_compute",
                    "resources_touched": ["epic:summary-projection-validation"],
                    "observed_result_classification": "cards_epic_run_started",
                    "receipt_refs": ["admission-1"],
                    "closure_classification": "step_completed",
                },
            },
        )
