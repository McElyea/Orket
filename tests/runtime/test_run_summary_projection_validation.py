from __future__ import annotations

import pytest

from orket.runtime.run_summary import build_run_summary_payload, validate_run_summary_payload

_STARTED_AT = "2036-03-05T12:00:00+00:00"
_FINALIZED_AT = "2036-03-05T12:00:05+00:00"


def _run_identity(*, run_id: str) -> dict[str, object]:
    return {
        "run_id": run_id,
        "workload": "summary-projection-validation",
        "start_time": _STARTED_AT,
        "identity_scope": "session_bootstrap",
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
