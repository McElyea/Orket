from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.odr.context_continuity_live_proof import _call_role, run_live_scenario_mode
from scripts.odr.run_odr_single_vs_coordinated import _load_scenario_inputs, _load_scenarios

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = (
    REPO_ROOT / "docs" / "projects" / "odr_round_cap_probe" / "odr_round_cap_probe_lane_config.json"
)
REQUIRED_ARTIFACT_KEYS = (
    "root",
    "bootstrap_output",
    "inspectability_output",
    "compare_output",
    "verdict_output",
    "closeout_output",
)


@dataclass(frozen=True)
class ProbeRunSpec:
    probe_id: str
    source_lane: str
    source_config_path: Path
    source_compare_artifact_path: Path
    source_pair_id: str
    source_locked_budget: int
    source_stop_reason: str
    scenario_id: str
    architect_model: str
    architect_provider: str
    reviewer_model: str
    reviewer_provider: str
    execution_order: int


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_path(base_path: Path, raw: str) -> Path:
    candidate = Path(str(raw or "").strip())
    if not candidate.is_absolute():
        candidate = base_path.parent / candidate
    return candidate.resolve()


def load_probe_config(path: Path | None = None) -> dict[str, Any]:
    config_path = (path or DEFAULT_CONFIG_PATH).resolve()
    payload = _read_json(config_path)
    payload["config_path"] = str(config_path)
    for key in ("probe_registry", "output_schema", "reused_v1_state_contract"):
        raw = str(payload.get(key) or "").strip()
        if not raw:
            raise ValueError(f"Round-cap probe config missing {key}.")
        resolved = _resolve_path(config_path, raw)
        if not resolved.exists():
            raise FileNotFoundError(f"Round-cap probe dependency not found: {resolved}")
        payload[f"{key}_path"] = str(resolved)
    if str(payload.get("continuity_mode") or "").strip() != "v1_compiled_shared_state":
        raise ValueError("Round-cap probe must freeze continuity_mode=v1_compiled_shared_state.")
    payload["probe_budget"] = int(payload.get("probe_budget") or 0)
    if payload["probe_budget"] <= 0:
        raise ValueError("Round-cap probe budget must be positive.")
    payload["role_timeout_sec"] = int(payload.get("role_timeout_sec") or 300)
    if payload["role_timeout_sec"] <= 0:
        raise ValueError("Round-cap probe role_timeout_sec must be positive.")
    artifact_paths = dict(payload.get("artifact_paths") or {})
    for key in REQUIRED_ARTIFACT_KEYS:
        if not str(artifact_paths.get(key) or "").strip():
            raise ValueError(f"Round-cap probe artifact_paths missing {key}.")
    payload["artifact_paths"] = artifact_paths
    return payload


def load_probe_registry(config: dict[str, Any]) -> dict[str, Any]:
    registry_path = Path(str(config["probe_registry_path"]))
    payload = _read_json(registry_path)
    specs: list[ProbeRunSpec] = []
    for raw in sorted(list(payload.get("probe_runs") or []), key=lambda row: int(row["execution_order"])):
        spec = ProbeRunSpec(
            probe_id=str(raw["probe_id"]),
            source_lane=str(raw["source_lane"]),
            source_config_path=_resolve_path(registry_path, str(raw["source_config"])),
            source_compare_artifact_path=_resolve_path(registry_path, str(raw["source_compare_artifact"])),
            source_pair_id=str(raw["source_pair_id"]),
            source_locked_budget=int(raw["source_locked_budget"]),
            source_stop_reason=str(raw["source_stop_reason"]),
            scenario_id=str(raw["scenario_id"]),
            architect_model=str(raw["architect_model"]),
            architect_provider=str(raw["architect_provider"]),
            reviewer_model=str(raw["reviewer_model"]),
            reviewer_provider=str(raw["reviewer_provider"]),
            execution_order=int(raw["execution_order"]),
        )
        if not spec.source_config_path.exists():
            raise FileNotFoundError(f"Probe source config not found: {spec.source_config_path}")
        if not spec.source_compare_artifact_path.exists():
            raise FileNotFoundError(f"Probe source compare artifact not found: {spec.source_compare_artifact_path}")
        specs.append(spec)
    if not specs:
        raise ValueError("Round-cap probe registry must declare probe_runs.")
    payload["probe_runs"] = specs
    return payload


def resolve_artifact_path(config: dict[str, Any], artifact_key: str) -> Path:
    raw = str((config.get("artifact_paths") or {}).get(artifact_key) or "").strip()
    if not raw:
        raise KeyError(f"Round-cap probe artifact_paths missing {artifact_key}.")
    return (REPO_ROOT / raw).resolve()


def _inventory_rows(registry: dict[str, Any]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    rows: list[dict[str, Any]] = []
    for raw in list((registry.get("inventory_freeze") or {}).get("provider_models") or []):
        token = (str(raw.get("model_id") or ""), str(raw.get("provider") or ""))
        if token in seen:
            continue
        seen.add(token)
        rows.append({"model_id": token[0], "provider": token[1], "status": "pending"})
    return rows


async def _preflight_inventory(registry: dict[str, Any], *, role_timeout_sec: int) -> list[dict[str, Any]]:
    rows = _inventory_rows(registry)
    prompt = [
        {"role": "system", "content": "You are a health check. Reply briefly."},
        {"role": "user", "content": "Reply with OK only."},
    ]
    for row in rows:
        try:
            response_text, _raw, latency_ms, _tokens = await _call_role(
                model=str(row["model_id"]),
                provider_name=str(row["provider"]),
                messages=prompt,
                timeout_sec=role_timeout_sec,
            )
            row["status"] = "ok"
            row["latency_ms"] = latency_ms
            row["sample_response"] = response_text[:80]
        except Exception as exc:  # noqa: BLE001
            row["status"] = "error"
            row["error"] = f"{type(exc).__name__}: {exc}"
    return rows


def _inventory_status_map(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(str(row["model_id"]), str(row["provider"])): row for row in rows}


def _normalized_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "").strip()).lower()
    return sha256(normalized.encode("utf-8")).hexdigest()


def _source_input_content(round_payload: dict[str, Any], artifact_kind: str) -> str:
    for row in list(round_payload.get("source_inputs") or []):
        if str(row.get("artifact_kind") or "") == artifact_kind:
            return str(row.get("content") or "")
    return ""


def _movement_analysis(inspect_row: dict[str, Any], compare_row: dict[str, Any], *, probe_budget: int) -> dict[str, Any]:
    rounds = list(inspect_row.get("rounds") or [])
    requirement_hashes = [_normalized_hash(_source_input_content(round_row, "current_canonical_artifact")) for round_row in rounds]
    architect_hashes = [_normalized_hash(_source_input_content(round_row, "latest_architect_delta")) for round_row in rounds]
    auditor_hashes = [_normalized_hash(_source_input_content(round_row, "latest_auditor_critique")) for round_row in rounds]

    def _last_change_round(values: list[str]) -> int:
        if not values:
            return 0
        last = 1
        for index in range(1, len(values)):
            if values[index] != values[index - 1]:
                last = index + 1
        return last

    def _flatline_round(values: list[str]) -> int | None:
        if not values:
            return None
        for index in range(len(values)):
            if len(set(values[index:])) == 1:
                return index + 1
        return None

    last_any_change_round = 0
    for index in range(len(rounds)):
        changed = False
        if index == 0:
            changed = True
        else:
            changed = any(
                current[index] != current[index - 1]
                for current in (requirement_hashes, architect_hashes, auditor_hashes)
            )
        if changed:
            last_any_change_round = index + 1

    stop_reason = str(compare_row.get("stop_reason") or "NONE")
    if stop_reason != "MAX_ROUNDS":
        assessment = "not_round_cap_bound"
    elif last_any_change_round < int(probe_budget):
        assessment = "flatlined_before_cap"
    else:
        assessment = "round_cap_still_binding"
    return {
        "requirement_last_change_round": _last_change_round(requirement_hashes),
        "architect_last_change_round": _last_change_round(architect_hashes),
        "auditor_last_change_round": _last_change_round(auditor_hashes),
        "requirement_flatline_round": _flatline_round(requirement_hashes),
        "architect_flatline_round": _flatline_round(architect_hashes),
        "auditor_flatline_round": _flatline_round(auditor_hashes),
        "last_any_change_round": last_any_change_round,
        "round_cap_assessment": assessment,
    }


def _source_protocol_hardening(source_config_path: Path) -> dict[str, Any]:
    payload = _read_json(source_config_path)
    hardening = payload.get("protocol_hardening")
    return dict(hardening) if isinstance(hardening, dict) else {}


def _pair_compare_row(spec: ProbeRunSpec, compare_row: dict[str, Any], movement_analysis: dict[str, Any], probe_budget: int) -> dict[str, Any]:
    return {
        "probe_id": spec.probe_id,
        "pair_id": spec.source_pair_id,
        "source_lane": spec.source_lane,
        "source_locked_budget": spec.source_locked_budget,
        "source_stop_reason": spec.source_stop_reason,
        "probe_budget": int(probe_budget),
        "scenario_id": str(compare_row["scenario_id"]),
        "execution_status": "success",
        "converged": bool(compare_row["converged"]),
        "stop_reason": str(compare_row["stop_reason"]),
        "rounds_consumed": int(compare_row["rounds_consumed"]),
        "reopened_decision_count": int(compare_row["reopened_decision_count"]),
        "contradiction_count": int(compare_row["contradiction_count"]),
        "regression_count": int(compare_row["regression_count"]),
        "carry_forward_integrity": float(compare_row["carry_forward_integrity"]),
        "round_latency_ms": list(compare_row["round_latency_ms"]),
        "round_active_context_size_bytes": list(compare_row["round_active_context_size_bytes"]),
        "round_active_context_size_tokens": list(compare_row["round_active_context_size_tokens"]),
        "movement_analysis": movement_analysis,
    }


async def run_round_cap_probe(*, config_path: Path | None = None) -> dict[str, Any]:
    config = load_probe_config(config_path)
    registry = load_probe_registry(config)
    output_schema = _read_json(Path(str(config["output_schema_path"])))
    inventory_rows = await _preflight_inventory(registry, role_timeout_sec=int(config["role_timeout_sec"]))
    inventory_status = _inventory_status_map(inventory_rows)

    bootstrap_payload = {
        "schema_version": "odr.round_cap_probe.bootstrap.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "config_path": str(config["config_path"]),
        "probe_budget": int(config["probe_budget"]),
        "continuity_mode": str(config["continuity_mode"]),
        "probe_run_count": len(registry["probe_runs"]),
        "output_schema_snapshot": {
            "path": str(config["output_schema_path"]),
            "schema_version": str(output_schema.get("schema_version") or ""),
            "required_artifacts": list(output_schema.get("required_artifacts") or []),
        },
        "inventory_rows": inventory_rows,
        "probe_runs": [
            {
                "probe_id": spec.probe_id,
                "source_lane": spec.source_lane,
                "source_pair_id": spec.source_pair_id,
                "source_locked_budget": spec.source_locked_budget,
                "source_stop_reason": spec.source_stop_reason,
                "scenario_id": spec.scenario_id,
                "architect_model": spec.architect_model,
                "architect_provider": spec.architect_provider,
                "reviewer_model": spec.reviewer_model,
                "reviewer_provider": spec.reviewer_provider,
                "execution_order": spec.execution_order,
            }
            for spec in registry["probe_runs"]
        ],
    }
    bootstrap_output = resolve_artifact_path(config, "bootstrap_output")
    bootstrap_persisted = write_payload_with_diff_ledger(bootstrap_output, bootstrap_payload)

    scenario_index = {str(row["id"]): row for row in _load_scenarios()}
    inspectability_rows: list[dict[str, Any]] = []
    compare_rows: list[dict[str, Any]] = []
    for spec in registry["probe_runs"]:
        preflight_error = next(
            (
                str(row.get("error") or "inventory_preflight_error")
                for row in (
                    inventory_status.get((spec.architect_model, spec.architect_provider)),
                    inventory_status.get((spec.reviewer_model, spec.reviewer_provider)),
                )
                if isinstance(row, dict) and str(row.get("status") or "") != "ok"
            ),
            None,
        )
        if preflight_error is not None:
            inspectability_rows.append(
                {
                    "probe_id": spec.probe_id,
                    "source_lane": spec.source_lane,
                    "source_pair_id": spec.source_pair_id,
                    "scenario_id": spec.scenario_id,
                    "probe_budget": int(config["probe_budget"]),
                    "execution_status": "runtime_blocker",
                    "blocking_error": preflight_error,
                    "rounds": [],
                }
            )
            compare_rows.append(
                {
                    "probe_id": spec.probe_id,
                    "pair_id": spec.source_pair_id,
                    "source_lane": spec.source_lane,
                    "source_locked_budget": spec.source_locked_budget,
                    "source_stop_reason": spec.source_stop_reason,
                    "probe_budget": int(config["probe_budget"]),
                    "scenario_id": spec.scenario_id,
                    "execution_status": "runtime_blocker",
                    "converged": False,
                    "stop_reason": "RUNTIME_BLOCKER",
                    "rounds_consumed": 0,
                    "reopened_decision_count": 0,
                    "contradiction_count": 0,
                    "regression_count": 0,
                    "carry_forward_integrity": 0.0,
                    "round_latency_ms": [],
                    "round_active_context_size_bytes": [],
                    "round_active_context_size_tokens": [],
                    "movement_analysis": {"round_cap_assessment": "blocked"},
                }
            )
            continue
        scenario_input = _load_scenario_inputs(scenario_index[spec.scenario_id])
        scenario_config = {
            "config_path": str(config["config_path"]),
            "v1_state_contract_path": str(config["reused_v1_state_contract_path"]),
            "role_timeout_sec": int(config["role_timeout_sec"]),
            "protocol_hardening": _source_protocol_hardening(spec.source_config_path),
        }
        pair = type(
            "ProbePair",
            (),
            {
                "pair_id": spec.source_pair_id,
                "architect_model": spec.architect_model,
                "architect_provider": spec.architect_provider,
                "auditor_model": spec.reviewer_model,
                "auditor_provider": spec.reviewer_provider,
            },
        )()
        try:
            inspect_row, compare_row = await run_live_scenario_mode(
                config=scenario_config,
                pair=pair,
                scenario_input=scenario_input,
                continuity_mode=str(config["continuity_mode"]),
                locked_budget=int(config["probe_budget"]),
            )
            movement_analysis = _movement_analysis(
                inspect_row,
                compare_row,
                probe_budget=int(config["probe_budget"]),
            )
            inspectability_rows.append(
                {
                    "probe_id": spec.probe_id,
                    "source_lane": spec.source_lane,
                    "source_pair_id": spec.source_pair_id,
                    "source_locked_budget": spec.source_locked_budget,
                    "source_stop_reason": spec.source_stop_reason,
                    "scenario_id": spec.scenario_id,
                    "probe_budget": int(config["probe_budget"]),
                    "continuity_mode": str(config["continuity_mode"]),
                    "movement_analysis": movement_analysis,
                    **inspect_row,
                }
            )
            compare_rows.append(
                _pair_compare_row(
                    spec,
                    compare_row,
                    movement_analysis,
                    int(config["probe_budget"]),
                )
            )
        except Exception as exc:  # noqa: BLE001
            inspectability_rows.append(
                {
                    "probe_id": spec.probe_id,
                    "source_lane": spec.source_lane,
                    "source_pair_id": spec.source_pair_id,
                    "scenario_id": spec.scenario_id,
                    "probe_budget": int(config["probe_budget"]),
                    "execution_status": "runtime_blocker",
                    "blocking_error": f"{type(exc).__name__}: {exc}",
                    "rounds": [],
                }
            )
            compare_rows.append(
                {
                    "probe_id": spec.probe_id,
                    "pair_id": spec.source_pair_id,
                    "source_lane": spec.source_lane,
                    "source_locked_budget": spec.source_locked_budget,
                    "source_stop_reason": spec.source_stop_reason,
                    "probe_budget": int(config["probe_budget"]),
                    "scenario_id": spec.scenario_id,
                    "execution_status": "runtime_blocker",
                    "converged": False,
                    "stop_reason": "RUNTIME_BLOCKER",
                    "rounds_consumed": 0,
                    "reopened_decision_count": 0,
                    "contradiction_count": 0,
                    "regression_count": 0,
                    "carry_forward_integrity": 0.0,
                    "round_latency_ms": [],
                    "round_active_context_size_bytes": [],
                    "round_active_context_size_tokens": [],
                    "movement_analysis": {"round_cap_assessment": "blocked"},
                }
            )

    inspectability_payload = {
        "schema_version": "odr.round_cap_probe.inspectability.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "config_path": str(config["config_path"]),
        "probe_budget": int(config["probe_budget"]),
        "probe_runs": inspectability_rows,
    }
    inspectability_output = resolve_artifact_path(config, "inspectability_output")
    inspectability_persisted = write_payload_with_diff_ledger(inspectability_output, inspectability_payload)

    compare_payload = {
        "schema_version": "odr.round_cap_probe.compare.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "config_path": str(config["config_path"]),
        "probe_budget": int(config["probe_budget"]),
        "scenario_runs": compare_rows,
    }
    compare_output = resolve_artifact_path(config, "compare_output")
    compare_persisted = write_payload_with_diff_ledger(compare_output, compare_payload)

    verdict_rows = []
    raise_round_cap = False
    for row in compare_rows:
        movement = dict(row.get("movement_analysis") or {})
        assessment = str(movement.get("round_cap_assessment") or "unknown")
        if assessment == "round_cap_still_binding":
            raise_round_cap = True
        verdict_rows.append(
            {
                "probe_id": str(row["probe_id"]),
                "source_lane": str(row["source_lane"]),
                "scenario_id": str(row["scenario_id"]),
                "source_locked_budget": int(row["source_locked_budget"]),
                "probe_budget": int(row["probe_budget"]),
                "source_stop_reason": str(row["source_stop_reason"]),
                "probe_stop_reason": str(row["stop_reason"]),
                "rounds_consumed": int(row["rounds_consumed"]),
                "execution_status": str(row["execution_status"]),
                "round_cap_assessment": assessment,
                "last_any_change_round": movement.get("last_any_change_round"),
                "requirement_flatline_round": movement.get("requirement_flatline_round"),
            }
        )
    verdict_payload = {
        "schema_version": "odr.round_cap_probe.verdict.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "config_path": str(config["config_path"]),
        "probe_budget": int(config["probe_budget"]),
        "raise_round_cap_recommended": raise_round_cap,
        "probe_verdicts": verdict_rows,
    }
    verdict_output = resolve_artifact_path(config, "verdict_output")
    verdict_persisted = write_payload_with_diff_ledger(verdict_output, verdict_payload)

    closeout_payload = {
        "schema_version": "odr.round_cap_probe.closeout.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "config_path": str(config["config_path"]),
        "probe_budget": int(config["probe_budget"]),
        "raise_round_cap_recommended": raise_round_cap,
        "summary": (
            "At least one rerun still hit MAX_ROUNDS while changing through the 20-round probe."
            if raise_round_cap
            else "The 20-round probe did not show evidence that increasing the round cap alone is justified."
        ),
    }
    closeout_output = resolve_artifact_path(config, "closeout_output")
    closeout_persisted = write_payload_with_diff_ledger(closeout_output, closeout_payload)
    return {
        "bootstrap_output": str(bootstrap_output),
        "inspectability_output": str(inspectability_output),
        "compare_output": str(compare_output),
        "verdict_output": str(verdict_output),
        "closeout_output": str(closeout_output),
        "bootstrap_payload": bootstrap_persisted,
        "inspectability_payload": inspectability_persisted,
        "compare_payload": compare_persisted,
        "verdict_payload": verdict_persisted,
        "closeout_payload": closeout_persisted,
    }
