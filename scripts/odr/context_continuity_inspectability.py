from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.common.rerun_diff_ledger import _payload_digest
from scripts.odr.context_continuity_lane import PairSpec
from scripts.odr.context_continuity_v0_replay import build_v0_loaded_context, build_v0_replay_block
from scripts.odr.context_continuity_v1_state import build_v1_role_view, build_v1_shared_state

REQUIRED_ROLES = ("architect", "auditor")


def _stable_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _artifact_digest(value: Any) -> str:
    return _payload_digest({"artifact": value})


def _materialize_artifact(
    raw: dict[str, Any],
    *,
    default_kind: str,
    require_history_refs: bool = False,
) -> dict[str, Any]:
    artifact_id = str(raw.get("artifact_id") or "").strip()
    if not artifact_id:
        raise ValueError(f"{default_kind} is missing artifact_id.")

    has_content = "content" in raw
    has_payload = "payload" in raw
    if not has_content and not has_payload:
        raise ValueError(f"{default_kind} {artifact_id} must declare content or payload.")
    if has_content and has_payload:
        raise ValueError(f"{default_kind} {artifact_id} cannot declare both content and payload.")

    body = raw["content"] if has_content else raw["payload"]
    serialized = _stable_text(body)
    artifact = {
        "artifact_id": artifact_id,
        "artifact_kind": str(raw.get("artifact_kind") or default_kind),
        "artifact_body": body,
        "artifact_sha256": _artifact_digest(body),
        "utf8_bytes": len(serialized.encode("utf-8")),
    }

    authority_level = str(raw.get("authority_level") or "").strip()
    if authority_level:
        artifact["authority_level"] = authority_level

    source_history_refs = [str(item).strip() for item in list(raw.get("source_history_refs") or []) if str(item).strip()]
    if require_history_refs and not source_history_refs:
        raise ValueError(f"{default_kind} {artifact_id} must declare source_history_refs.")
    if source_history_refs:
        artifact["source_history_refs"] = source_history_refs

    notes = str(raw.get("notes") or "").strip()
    if notes:
        artifact["notes"] = notes
    builder_contract_path = str(raw.get("builder_contract_path") or "").strip()
    if builder_contract_path:
        artifact["builder_contract_path"] = builder_contract_path
    builder_contract_sha256 = str(raw.get("builder_contract_sha256") or "").strip()
    if builder_contract_sha256:
        artifact["builder_contract_sha256"] = builder_contract_sha256
    return artifact


def _validate_ref_map(
    refs: list[dict[str, Any]],
    *,
    key: str,
    known_ids: set[str],
    label: str,
) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for raw in refs:
        ref_id = str(raw.get(key) or "").strip()
        if not ref_id:
            raise ValueError(f"{label} is missing {key}.")
        if ref_id not in known_ids:
            raise ValueError(f"{label} references unknown {key}={ref_id}.")
        relationship = str(raw.get("relationship") or "").strip()
        if not relationship:
            raise ValueError(f"{label} {ref_id} is missing relationship.")
        normalized.append({key: ref_id, "relationship": relationship})
    return normalized


def _materialize_projection(
    raw: dict[str, Any] | None,
    *,
    role: str,
    source_input_ids: set[str],
    mode_artifact_ids: set[str],
    required: bool,
) -> dict[str, Any] | None:
    if raw is None:
        if required:
            raise ValueError(f"role_view_projection is required for role={role}.")
        return None

    artifact = _materialize_artifact(raw, default_kind="role_view_projection")
    source_refs = _validate_ref_map(
        list((raw.get("derived_from") or {}).get("source_input_refs") or []),
        key="source_input_id",
        known_ids=source_input_ids,
        label=f"role_view_projection[{role}]",
    )
    mode_refs = _validate_ref_map(
        list((raw.get("derived_from") or {}).get("mode_artifact_refs") or []),
        key="artifact_id",
        known_ids=mode_artifact_ids,
        label=f"role_view_projection[{role}]",
    )
    artifact["derived_from"] = {
        "source_input_refs": source_refs,
        "mode_artifact_refs": mode_refs,
    }
    return artifact


def _materialize_role_view(
    raw: dict[str, Any],
    *,
    continuity_mode: str,
    source_input_ids: set[str],
    mode_artifact_ids: set[str],
    replay_block_artifact: dict[str, Any] | None,
    shared_state_artifact: dict[str, Any] | None,
    config_path: str,
    v1_state_contract_path: str,
    prior_round_loaded_context_sha256: str | None,
    prior_round_state_sha256: str | None,
    require_projection: bool,
) -> dict[str, Any]:
    role = str(raw.get("role") or "").strip()
    if role not in REQUIRED_ROLES:
        raise ValueError(f"Unsupported role in inspectability artifact: {role!r}.")

    loaded_context = str(raw.get("loaded_context") or "")
    loaded_context_delivery: dict[str, str] | None = None
    role_focus = str(raw.get("role_focus") or "").strip()
    if continuity_mode == "v0_log_derived_replay" and role_focus:
        if loaded_context.strip():
            raise ValueError(f"role={role} may not declare both loaded_context and role_focus in V0.")
        if replay_block_artifact is None:
            raise ValueError("V0 loaded_context generation requires replay_block artifact.")
        loaded_context_delivery = build_v0_loaded_context(
            replay_block_artifact,
            role=role,
            config_path=Path(config_path),
            role_focus=role_focus,
        )
        loaded_context = str(loaded_context_delivery["text"])
    if continuity_mode == "v1_compiled_shared_state" and role_focus:
        if loaded_context.strip():
            raise ValueError(f"role={role} may not declare both loaded_context and role_focus in V1.")
        if shared_state_artifact is None:
            raise ValueError("V1 loaded_context generation requires shared_state_snapshot artifact.")
        loaded_context_delivery = build_v1_role_view(
            shared_state_artifact,
            role=role,
            role_focus=role_focus,
            contract_path=Path(v1_state_contract_path),
        )
        loaded_context = str(loaded_context_delivery["loaded_context"])
    if not loaded_context:
        raise ValueError(f"loaded_context is required for role={role}.")
    source_refs = _validate_ref_map(
        list((raw.get("derived_from") or {}).get("source_input_refs") or []),
        key="source_input_id",
        known_ids=source_input_ids,
        label=f"loaded_context[{role}]",
    )
    if not source_refs:
        raise ValueError(f"loaded_context[{role}] must declare at least one source_input_ref.")
    mode_refs = _validate_ref_map(
        list((raw.get("derived_from") or {}).get("mode_artifact_refs") or []),
        key="artifact_id",
        known_ids=mode_artifact_ids,
        label=f"loaded_context[{role}]",
    )

    loaded_context_artifact = {
        "artifact_sha256": _artifact_digest(loaded_context),
        "text": loaded_context,
        "utf8_bytes": len(loaded_context.encode("utf-8")),
        "provider_request_token_count": raw.get("provider_request_token_count"),
    }
    if loaded_context_artifact["provider_request_token_count"] is None:
        loaded_context_artifact["provider_request_token_count"] = None
    if loaded_context_delivery is not None:
        loaded_context_artifact["delivery_mode"] = str(loaded_context_delivery["delivery_mode"])
        loaded_context_artifact["loader_contract_path"] = str(loaded_context_delivery["loader_contract_path"])
        loaded_context_artifact["loader_contract_sha256"] = str(loaded_context_delivery["loader_contract_sha256"])
        if continuity_mode == "v0_log_derived_replay":
            loaded_context_artifact["replay_block_sha256"] = str(loaded_context_delivery["replay_block_sha256"])
        if continuity_mode == "v1_compiled_shared_state":
            loaded_context_artifact["shared_state_sha256"] = str(loaded_context_delivery["shared_state_sha256"])

    projection_raw = raw.get("role_view_projection")
    if continuity_mode == "v1_compiled_shared_state" and role_focus:
        projection_raw = {
            "artifact_id": f"{str(shared_state_artifact['artifact_id'])}_{role}_projection",
            "artifact_kind": "role_view_projection",
            "content": str(loaded_context_delivery["projection_text"]),
            "derived_from": raw.get("derived_from") or {},
        }

    return {
        "role": role,
        "loaded_context_artifact": loaded_context_artifact,
        "derived_from": {
            "source_input_refs": source_refs,
            "mode_artifact_refs": mode_refs,
        },
        "predecessor_linkage": {
            "prior_round_loaded_context_sha256": prior_round_loaded_context_sha256,
            "prior_round_state_sha256": prior_round_state_sha256,
        },
        "role_view_projection": _materialize_projection(
            projection_raw,
            role=role,
            source_input_ids=source_input_ids,
            mode_artifact_ids=mode_artifact_ids,
            required=require_projection,
        ),
    }


def _materialize_mode_artifacts(
    raw: dict[str, Any],
    *,
    continuity_mode: str,
    config_path: str,
    v1_state_contract_path: str,
    source_inputs: list[dict[str, Any]],
    round_index: int,
    prior_state_payload: dict[str, Any] | None,
) -> tuple[dict[str, Any], str | None]:
    replay_block_raw = raw.get("replay_block")
    replay_builder_input = raw.get("replay_builder_input")
    shared_state_raw = raw.get("shared_state_snapshot")
    shared_state_builder_input = raw.get("shared_state_builder_input")

    if continuity_mode == "control_current_replay" and (
        replay_block_raw or replay_builder_input or shared_state_raw or shared_state_builder_input
    ):
        raise ValueError("control_current_replay may not declare replay artifacts or shared_state_snapshot.")
    if continuity_mode == "v0_log_derived_replay" and (shared_state_raw or shared_state_builder_input):
        raise ValueError("v0_log_derived_replay may not declare shared_state_snapshot.")
    if continuity_mode == "v1_compiled_shared_state" and replay_block_raw:
        raise ValueError("v1_compiled_shared_state may not declare replay_block.")
    if replay_block_raw and replay_builder_input:
        raise ValueError("V0 mode_artifacts may not declare both replay_block and replay_builder_input.")
    if shared_state_raw and shared_state_builder_input:
        raise ValueError("V1 mode_artifacts may not declare both shared_state_snapshot and shared_state_builder_input.")

    if continuity_mode == "v0_log_derived_replay" and replay_builder_input:
        replay_block_raw = build_v0_replay_block(
            list(dict(replay_builder_input).get("source_history") or []),
            artifact_id=str(dict(replay_builder_input).get("artifact_id") or "").strip(),
            config_path=Path(config_path),
        )
    if continuity_mode == "v1_compiled_shared_state" and shared_state_builder_input:
        builder_input = dict(shared_state_builder_input)
        current_requirement = ""
        for item in source_inputs:
            if str(item.get("artifact_kind") or "") == "current_canonical_artifact":
                current_requirement = str(item.get("artifact_body") or "")
                break
        shared_state_raw = build_v1_shared_state(
            source_inputs=source_inputs,
            current_requirement=current_requirement,
            round_index=round_index,
            artifact_id=str(builder_input.get("artifact_id") or "").strip(),
            latest_trace=dict(builder_input.get("latest_trace") or {}) or None,
            prior_state_payload=prior_state_payload,
            contract_path=Path(v1_state_contract_path),
        )

    replay_block = (
        _materialize_artifact(
            replay_block_raw,
            default_kind="replay_block",
            require_history_refs=True,
        )
        if isinstance(replay_block_raw, dict)
        else None
    )
    shared_state_snapshot = (
        _materialize_artifact(shared_state_raw, default_kind="shared_state_snapshot")
        if isinstance(shared_state_raw, dict)
        else None
    )

    if continuity_mode == "v0_log_derived_replay" and replay_block is None:
        raise ValueError("v0_log_derived_replay requires replay_block.")
    if continuity_mode == "v1_compiled_shared_state" and shared_state_snapshot is None:
        raise ValueError("v1_compiled_shared_state requires shared_state_snapshot.")

    round_state_sha256 = None
    if shared_state_snapshot is not None:
        round_state_sha256 = str(shared_state_snapshot["artifact_sha256"])
    elif replay_block is not None:
        round_state_sha256 = str(replay_block["artifact_sha256"])

    return {
        "replay_block": replay_block,
        "shared_state_snapshot": shared_state_snapshot,
    }, round_state_sha256


def _validate_roles(raw_role_views: list[dict[str, Any]]) -> list[dict[str, Any]]:
    roles = [str(item.get("role") or "").strip() for item in raw_role_views]
    if len([role for role in roles if role]) != len(REQUIRED_ROLES):
        raise ValueError(f"role_views must contain exactly {len(REQUIRED_ROLES)} named roles.")
    if len(set(roles)) != len(roles):
        raise ValueError("role_views may not contain duplicate roles.")

    ordered: list[dict[str, Any]] = []
    by_role = {role: item for role, item in zip(roles, raw_role_views, strict=False)}
    for role in REQUIRED_ROLES:
        if role not in by_role:
            raise ValueError(f"role_views is missing role={role}.")
        ordered.append(by_role[role])
    if len(by_role) != len(REQUIRED_ROLES):
        extras = sorted(set(by_role) - set(REQUIRED_ROLES))
        raise ValueError(f"role_views contains unsupported roles: {extras}.")
    return ordered


def build_inspectability_payload(config: dict[str, Any], inspectability_input: dict[str, Any]) -> dict[str, Any]:
    scenario_runs_raw = list(inspectability_input.get("scenario_runs") or [])
    if not scenario_runs_raw:
        raise ValueError("Inspectability input must declare scenario_runs.")

    allowed_pair_ids = {
        pair.pair_id
        for pair in [
            *list(config.get("selected_primary_pairs") or []),
            *list(config.get("secondary_sensitivity_pairs") or []),
        ]
        if isinstance(pair, PairSpec)
    }
    if not allowed_pair_ids:
        raise ValueError("Lane config does not declare any allowed pair ids.")

    scenario_run_artifacts: list[dict[str, Any]] = []
    for raw_run in scenario_runs_raw:
        pair_id = str(raw_run.get("pair_id") or "").strip()
        scenario_id = str(raw_run.get("scenario_id") or "").strip()
        continuity_mode = str(raw_run.get("continuity_mode") or "").strip()
        locked_budget = int(raw_run.get("locked_budget") or 0)

        if pair_id not in allowed_pair_ids:
            raise ValueError(f"Inspectability input pair_id is not pre-registered: {pair_id!r}.")
        if scenario_id not in set(config["scenario_set"]["scenario_ids"]):
            raise ValueError(f"Inspectability input scenario_id is outside the locked scenario set: {scenario_id!r}.")
        if continuity_mode not in set(config["continuity_modes"]):
            raise ValueError(f"Inspectability input continuity_mode is not locked in the lane config: {continuity_mode!r}.")
        if locked_budget not in set(config["locked_budgets"]):
            raise ValueError(f"Inspectability input locked_budget is not a locked lane budget: {locked_budget!r}.")

        raw_rounds = list(raw_run.get("rounds") or [])
        if not raw_rounds:
            raise ValueError(f"Inspectability input scenario_run {scenario_id} must declare rounds.")

        prior_role_hashes = {role: None for role in REQUIRED_ROLES}
        prior_round_state_sha256: str | None = None
        round_artifacts: list[dict[str, Any]] = []
        seen_round_indices: set[int] = set()
        for raw_round in sorted(raw_rounds, key=lambda item: int(item.get("round_index") or 0)):
            round_index = int(raw_round.get("round_index") or 0)
            if round_index in seen_round_indices:
                raise ValueError(f"Duplicate round_index in inspectability input: {round_index}.")
            seen_round_indices.add(round_index)
            why_loaded_context_changed = str(raw_round.get("why_loaded_context_changed") or "").strip()
            if not why_loaded_context_changed:
                raise ValueError(f"round_index={round_index} must declare why_loaded_context_changed.")

            source_inputs = [
                _materialize_artifact(raw_item, default_kind="source_input")
                for raw_item in list(raw_round.get("source_inputs") or [])
            ]
            source_input_ids = {str(item["artifact_id"]) for item in source_inputs}
            if not source_input_ids:
                raise ValueError(f"round_index={round_index} must declare source_inputs.")

            mode_artifacts, round_state_sha256 = _materialize_mode_artifacts(
                dict(raw_round.get("mode_artifacts") or {}),
                continuity_mode=continuity_mode,
                config_path=str(config["config_path"]),
                v1_state_contract_path=str(config["v1_state_contract_path"]),
                source_inputs=source_inputs,
                round_index=round_index,
                prior_state_payload=(
                    round_artifacts[-1]["mode_artifacts"]["shared_state_snapshot"]["artifact_body"]
                    if round_artifacts
                    and continuity_mode == "v1_compiled_shared_state"
                    and isinstance(round_artifacts[-1]["mode_artifacts"].get("shared_state_snapshot"), dict)
                    else None
                ),
            )
            mode_artifact_ids = {
                str(item["artifact_id"])
                for item in mode_artifacts.values()
                if isinstance(item, dict)
            }
            if len(mode_artifact_ids) != len([item for item in mode_artifacts.values() if isinstance(item, dict)]):
                raise ValueError(f"round_index={round_index} contains duplicate mode artifact ids.")

            role_views = [
                _materialize_role_view(
                    raw_role_view,
                    continuity_mode=continuity_mode,
                    source_input_ids=source_input_ids,
                    mode_artifact_ids=mode_artifact_ids,
                    replay_block_artifact=mode_artifacts["replay_block"],
                    shared_state_artifact=mode_artifacts["shared_state_snapshot"],
                    config_path=str(config["config_path"]),
                    v1_state_contract_path=str(config["v1_state_contract_path"]),
                    prior_round_loaded_context_sha256=prior_role_hashes[str(raw_role_view["role"])],
                    prior_round_state_sha256=prior_round_state_sha256,
                    require_projection=continuity_mode == "v1_compiled_shared_state",
                )
                for raw_role_view in _validate_roles(list(raw_round.get("role_views") or []))
            ]

            round_artifacts.append(
                {
                    "round_index": round_index,
                    "continuity_mode": continuity_mode,
                    "why_loaded_context_changed": why_loaded_context_changed,
                    "source_inputs": source_inputs,
                    "mode_artifacts": mode_artifacts,
                    "predecessor_linkage": {
                        "prior_round_role_artifact_sha256": {
                            role: prior_role_hashes[role] for role in REQUIRED_ROLES
                        },
                        "prior_round_state_sha256": prior_round_state_sha256,
                    },
                    "role_views": role_views,
                }
            )

            prior_role_hashes = {
                str(role_view["role"]): str(role_view["loaded_context_artifact"]["artifact_sha256"])
                for role_view in role_views
            }
            prior_round_state_sha256 = round_state_sha256

        scenario_run_artifacts.append(
            {
                "pair_id": pair_id,
                "scenario_id": scenario_id,
                "continuity_mode": continuity_mode,
                "locked_budget": locked_budget,
                "round_artifacts": round_artifacts,
            }
        )

    return {
        "schema_version": "odr.context_continuity.inspectability.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "ended_at": datetime.now(UTC).isoformat(),
        "lane_config_snapshot": {
            "requirements_authority": str(config["requirements_authority"]),
            "implementation_authority": str(config["implementation_authority"]),
            "continuity_modes": list(config["continuity_modes"]),
            "locked_budgets": list(config["locked_budgets"]),
            "pair_scope": str(config["pair_scope"]),
            "scenario_set": dict(config["scenario_set"]),
        },
        "evidence_scope": str(config["pair_scope"]),
        "artifact_locations": dict(config["artifact_paths"]),
        "scenario_run_artifacts": scenario_run_artifacts,
    }
