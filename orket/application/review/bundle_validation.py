from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orket.application.review.control_plane_projection import (
    validate_review_control_plane_ref_hierarchy,
    validate_review_control_plane_ref_run_lineage,
    validate_review_execution_state_payload,
    validate_review_matching_identifier,
    validate_review_required_identifier,
)


def _load_review_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_validated_review_payload(
    path: Path,
    *,
    field_name: str,
    authoritative_flag_field: str,
) -> dict[str, Any]:
    payload = _load_review_json(path)
    validated = validate_review_execution_state_payload(
        payload,
        field_name=field_name,
        authoritative_flag_field=authoritative_flag_field,
    )
    return dict(validated)


def _load_required_review_json_object(path: Path, *, field_name: str) -> dict[str, Any]:
    try:
        payload = _load_review_json(path)
    except FileNotFoundError as exc:
        raise ValueError(f"{field_name}_missing") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{field_name}_json_object_required")
    return dict(payload)

def _validate_review_bundle_identity_alignment(
    manifest: dict[str, Any],
    payload: dict[str, Any],
    *,
    field_name: str,
) -> dict[str, Any]:
    normalized_manifest = dict(manifest)
    normalized_payload = dict(payload)

    manifest_run_id = validate_review_required_identifier(
        normalized_manifest.get("run_id"),
        error="review_run_manifest_run_id_missing",
    )
    manifest_control_plane_run_id = str(normalized_manifest.get("control_plane_run_id") or "").strip()
    manifest_control_plane_attempt_id = str(normalized_manifest.get("control_plane_attempt_id") or "").strip()
    manifest_control_plane_step_id = str(normalized_manifest.get("control_plane_step_id") or "").strip()

    validate_review_control_plane_ref_hierarchy(
        control_plane_run_id=manifest_control_plane_run_id,
        control_plane_attempt_id=manifest_control_plane_attempt_id,
        control_plane_step_id=manifest_control_plane_step_id,
        run_id_error="review_run_manifest_control_plane_run_id_missing",
        attempt_id_error="review_run_manifest_control_plane_attempt_id_missing",
    )

    validate_review_matching_identifier(
        manifest_control_plane_run_id,
        expected=manifest_run_id,
        error="review_run_manifest_control_plane_run_id_mismatch",
    )
    if manifest_control_plane_run_id:
        validate_review_control_plane_ref_run_lineage(
            control_plane_run_id=manifest_control_plane_run_id,
            control_plane_attempt_id=manifest_control_plane_attempt_id,
            control_plane_step_id=manifest_control_plane_step_id,
            attempt_id_error="review_run_manifest_control_plane_attempt_id_run_lineage_mismatch",
            step_id_error="review_run_manifest_control_plane_step_id_run_lineage_mismatch",
        )

    payload_run_id = validate_review_required_identifier(
        normalized_payload.get("run_id"),
        error=f"{field_name}_run_id_missing",
    )
    if payload_run_id != manifest_run_id:
        raise ValueError(f"{field_name}_run_id_mismatch")

    expected_control_plane_run_id = manifest_control_plane_run_id or manifest_run_id
    payload_control_plane_run_id = str(normalized_payload.get("control_plane_run_id") or "").strip()
    if manifest_control_plane_run_id and not payload_control_plane_run_id:
        raise ValueError(f"{field_name}_control_plane_run_id_missing")
    if expected_control_plane_run_id and payload_control_plane_run_id:
        validate_review_matching_identifier(
            payload_control_plane_run_id,
            expected=expected_control_plane_run_id,
            error=f"{field_name}_control_plane_run_id_mismatch",
        )
    elif payload_run_id and payload_control_plane_run_id and payload_control_plane_run_id != payload_run_id:
        raise ValueError(f"{field_name}_control_plane_run_id_mismatch")

    payload_control_plane_attempt_id = str(normalized_payload.get("control_plane_attempt_id") or "").strip()
    payload_control_plane_step_id = str(normalized_payload.get("control_plane_step_id") or "").strip()

    validate_review_control_plane_ref_hierarchy(
        control_plane_run_id=payload_control_plane_run_id,
        control_plane_attempt_id=payload_control_plane_attempt_id,
        control_plane_step_id=payload_control_plane_step_id,
        run_id_error=f"{field_name}_control_plane_run_id_missing",
        attempt_id_error=f"{field_name}_control_plane_attempt_id_missing",
    )
    if payload_control_plane_run_id:
        validate_review_control_plane_ref_run_lineage(
            control_plane_run_id=payload_control_plane_run_id,
            control_plane_attempt_id=payload_control_plane_attempt_id,
            control_plane_step_id=payload_control_plane_step_id,
            attempt_id_error=f"{field_name}_control_plane_attempt_id_run_lineage_mismatch",
            step_id_error=f"{field_name}_control_plane_step_id_run_lineage_mismatch",
        )

    if manifest_control_plane_attempt_id and not payload_control_plane_attempt_id:
        raise ValueError(f"{field_name}_control_plane_attempt_id_missing")
    if (
        manifest_control_plane_attempt_id
        and payload_control_plane_attempt_id
        and payload_control_plane_attempt_id != manifest_control_plane_attempt_id
    ):
        raise ValueError(f"{field_name}_control_plane_attempt_id_mismatch")

    if manifest_control_plane_step_id and not payload_control_plane_step_id:
        raise ValueError(f"{field_name}_control_plane_step_id_missing")
    if (
        manifest_control_plane_step_id
        and payload_control_plane_step_id
        and payload_control_plane_step_id != manifest_control_plane_step_id
    ):
        raise ValueError(f"{field_name}_control_plane_step_id_mismatch")

    return normalized_payload


def load_validated_review_run_bundle_payloads(run_dir: Path) -> dict[str, dict[str, Any] | None]:
    manifest = _load_validated_review_payload(
        run_dir / "run_manifest.json",
        field_name="review_run_manifest",
        authoritative_flag_field="lane_outputs_execution_state_authoritative",
    )
    deterministic = _load_validated_review_payload(
        run_dir / "deterministic_decision.json",
        field_name="deterministic_review_decision",
        authoritative_flag_field="lane_output_execution_state_authoritative",
    )
    deterministic = _validate_review_bundle_identity_alignment(
        manifest,
        deterministic,
        field_name="deterministic_review_decision",
    )
    model_payload: dict[str, Any] | None = None
    model_path = run_dir / "model_assisted_critique.json"
    if model_path.is_file():
        model_payload = _load_validated_review_payload(
            model_path,
            field_name="model_assisted_critique",
            authoritative_flag_field="lane_output_execution_state_authoritative",
        )
        model_payload = _validate_review_bundle_identity_alignment(
            manifest,
            model_payload,
            field_name="model_assisted_critique",
        )
    return {
        "manifest": manifest,
        "deterministic": deterministic,
        "model_assisted": model_payload,
    }


def load_validated_review_run_bundle_artifacts(
    run_dir: Path,
    *,
    require_policy_resolved: bool = False,
) -> dict[str, dict[str, Any] | None]:
    payloads = load_validated_review_run_bundle_payloads(run_dir)
    snapshot_payload = _load_required_review_json_object(
        run_dir / "snapshot.json",
        field_name="review_run_snapshot",
    )
    policy_payload: dict[str, Any] | None = None
    policy_path = run_dir / "policy_resolved.json"
    if require_policy_resolved or policy_path.is_file():
        policy_payload = _load_required_review_json_object(
            policy_path,
            field_name="review_run_resolved_policy",
        )
    return {
        **payloads,
        "snapshot": snapshot_payload,
        "policy_resolved": policy_payload,
    }


def _resolve_review_replay_bundle_dir(snapshot_path: Path, policy_path: Path) -> Path | None:
    if snapshot_path.parent != policy_path.parent:
        return None
    if snapshot_path.name != "snapshot.json" or policy_path.name != "policy_resolved.json":
        return None
    run_dir = snapshot_path.parent
    marker_paths = (
        run_dir / "run_manifest.json",
        run_dir / "deterministic_decision.json",
        run_dir / "model_assisted_critique.json",
    )
    if not any(path.is_file() for path in marker_paths):
        return None
    return run_dir


def load_review_replay_artifacts(
    *,
    run_dir: Path | None = None,
    snapshot_path: Path | None = None,
    policy_path: Path | None = None,
) -> dict[str, dict[str, Any] | None]:
    if run_dir is not None:
        return load_validated_review_run_bundle_artifacts(
            run_dir,
            require_policy_resolved=True,
        )
    if snapshot_path is None or policy_path is None:
        raise ValueError("review_replay_artifacts_require_run_dir_or_snapshot_and_policy")
    canonical_run_dir = _resolve_review_replay_bundle_dir(snapshot_path, policy_path)
    if canonical_run_dir is not None:
        return load_validated_review_run_bundle_artifacts(
            canonical_run_dir,
            require_policy_resolved=True,
        )
    return {
        "manifest": None,
        "deterministic": None,
        "model_assisted": None,
        "snapshot": _load_required_review_json_object(
            snapshot_path,
            field_name="review_run_snapshot",
        ),
        "policy_resolved": _load_required_review_json_object(
            policy_path,
            field_name="review_run_resolved_policy",
        ),
    }


def validate_review_run_bundle_authority_markers(run_dir: Path) -> None:
    load_validated_review_run_bundle_payloads(run_dir)
