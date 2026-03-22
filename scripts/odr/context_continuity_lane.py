from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LANE_CONFIG_PATH = (
    REPO_ROOT
    / "docs"
    / "projects"
    / "archive"
    / "ContextContinuity"
    / "CC03212026"
    / "odr_context_continuity_lane_config.json"
)
REQUIRED_CONTINUITY_MODES = (
    "control_current_replay",
    "v0_log_derived_replay",
    "v1_compiled_shared_state",
)
REQUIRED_ARTIFACT_PATH_KEYS = (
    "root",
    "bootstrap_summary",
    "inspectability_output",
    "compare_output",
    "verdict_output",
)


@dataclass(frozen=True)
class PairSpec:
    pair_id: str
    architect_model: str
    architect_provider: str
    auditor_model: str
    auditor_provider: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PairSpec":
        return cls(
            pair_id=str(raw["pair_id"]),
            architect_model=str(raw["architect_model"]),
            architect_provider=str(raw["architect_provider"]),
            auditor_model=str(raw["auditor_model"]),
            auditor_provider=str(raw["auditor_provider"]),
        )

    def as_dict(self) -> dict[str, str]:
        return {
            "pair_id": self.pair_id,
            "architect_model": self.architect_model,
            "architect_provider": self.architect_provider,
            "auditor_model": self.auditor_model,
            "auditor_provider": self.auditor_provider,
        }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_path(config_path: Path, raw: str) -> Path:
    candidate = Path(str(raw or "").strip())
    if not candidate.is_absolute():
        candidate = config_path.parent / candidate
    return candidate.resolve()


def _validate_modes(modes: list[str]) -> list[str]:
    normalized = [str(mode).strip() for mode in modes if str(mode).strip()]
    if tuple(normalized) != REQUIRED_CONTINUITY_MODES:
        raise ValueError(
            "Lane config continuity_modes must exactly match "
            f"{list(REQUIRED_CONTINUITY_MODES)}."
        )
    return normalized


def load_lane_config(path: Path | None = None) -> dict[str, Any]:
    config_path = (path or DEFAULT_LANE_CONFIG_PATH).resolve()
    payload = _read_json(config_path)
    payload["config_path"] = str(config_path)
    payload["continuity_modes"] = _validate_modes(list(payload.get("continuity_modes") or []))

    locked_budgets = [int(budget) for budget in list(payload.get("locked_budgets") or [])]
    if not locked_budgets or any(budget <= 0 for budget in locked_budgets):
        raise ValueError("Lane config must declare positive locked_budgets.")
    payload["locked_budgets"] = locked_budgets

    scenario_ids = [str(item).strip() for item in list((payload.get("scenario_set") or {}).get("scenario_ids") or [])]
    if not scenario_ids:
        raise ValueError("Lane config must declare a non-empty scenario_set.scenario_ids list.")

    primary_pairs = [PairSpec.from_dict(row) for row in list(payload.get("selected_primary_pairs") or [])]
    if not primary_pairs:
        raise ValueError("Lane config must declare at least one selected_primary_pairs entry.")
    payload["selected_primary_pairs"] = primary_pairs
    payload["secondary_sensitivity_pairs"] = [
        PairSpec.from_dict(row) for row in list(payload.get("secondary_sensitivity_pairs") or [])
    ]

    mode_state_inputs = dict(payload.get("mode_state_inputs") or {})
    for mode in REQUIRED_CONTINUITY_MODES:
        if mode not in mode_state_inputs:
            raise ValueError(f"Lane config mode_state_inputs missing {mode}.")
        if mode == "control_current_replay" and list(mode_state_inputs.get(mode) or []):
            raise ValueError("control_current_replay must not depend on V0 or V1 state inputs.")
    payload["mode_state_inputs"] = {
        str(mode): [str(item) for item in list(items or [])]
        for mode, items in mode_state_inputs.items()
    }

    artifact_paths = dict(payload.get("artifact_paths") or {})
    for key in REQUIRED_ARTIFACT_PATH_KEYS:
        value = str(artifact_paths.get(key) or "").strip()
        if not value:
            raise ValueError(f"Lane config artifact_paths missing {key}.")
    payload["artifact_paths"] = artifact_paths

    raw_prereg = str(payload.get("pre_registration_record") or "").strip()
    raw_output_schema = str(payload.get("output_schema") or "").strip()
    raw_v0_replay_contract = str(payload.get("v0_replay_contract") or "").strip()
    raw_v1_state_contract = str(payload.get("v1_state_contract") or "").strip()
    if not raw_prereg:
        raise ValueError("Lane config must declare pre_registration_record.")
    if not raw_output_schema:
        raise ValueError("Lane config must declare output_schema.")
    if not raw_v0_replay_contract:
        raise ValueError("Lane config must declare v0_replay_contract.")
    if not raw_v1_state_contract:
        raise ValueError("Lane config must declare v1_state_contract.")

    prereg_path = _resolve_path(config_path, raw_prereg)
    output_schema_path = _resolve_path(config_path, raw_output_schema)
    v0_replay_contract_path = _resolve_path(config_path, raw_v0_replay_contract)
    v1_state_contract_path = _resolve_path(config_path, raw_v1_state_contract)
    if not prereg_path.exists():
        raise FileNotFoundError(f"Pre-registration record not found: {prereg_path}")
    if not output_schema_path.exists():
        raise FileNotFoundError(f"Output schema not found: {output_schema_path}")
    if not v0_replay_contract_path.exists():
        raise FileNotFoundError(f"V0 replay contract not found: {v0_replay_contract_path}")
    if not v1_state_contract_path.exists():
        raise FileNotFoundError(f"V1 state contract not found: {v1_state_contract_path}")
    payload["pre_registration_record_path"] = str(prereg_path)
    payload["output_schema_path"] = str(output_schema_path)
    payload["v0_replay_contract_path"] = str(v0_replay_contract_path)
    payload["v1_state_contract_path"] = str(v1_state_contract_path)
    return payload


def load_pair_preregistration(config: dict[str, Any]) -> dict[str, Any]:
    return _read_json(Path(str(config["pre_registration_record_path"])))


def load_output_schema(config: dict[str, Any]) -> dict[str, Any]:
    return _read_json(Path(str(config["output_schema_path"])))


def load_v0_replay_contract(config: dict[str, Any]) -> dict[str, Any]:
    return _read_json(Path(str(config["v0_replay_contract_path"])))


def load_v1_state_contract(config: dict[str, Any]) -> dict[str, Any]:
    return _read_json(Path(str(config["v1_state_contract_path"])))


def build_continuity_mode_registry(config: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "mode": mode,
            "state_inputs_required": list(config["mode_state_inputs"][mode]),
        }
        for mode in config["continuity_modes"]
    ]


def build_pair_budget_aggregate(
    scenario_runs: list[dict[str, Any]],
    *,
    pair_id: str,
    locked_budget: int,
    continuity_mode: str,
) -> dict[str, Any]:
    if not scenario_runs:
        raise ValueError("build_pair_budget_aggregate requires at least one scenario-run.")

    token_samples = [
        float(row["median_round_active_context_size_tokens"])
        for row in scenario_runs
        if row.get("median_round_active_context_size_tokens") is not None
    ]

    return {
        "pair_id": pair_id,
        "locked_budget": int(locked_budget),
        "continuity_mode": str(continuity_mode),
        "scenario_run_count": len(scenario_runs),
        "convergence_rate": sum(1.0 if bool(row["converged"]) else 0.0 for row in scenario_runs) / len(scenario_runs),
        "reopened_decision_rate": sum(float(row["reopened_decision_count"]) for row in scenario_runs) / len(scenario_runs),
        "contradiction_rate": sum(float(row["contradiction_count"]) for row in scenario_runs) / len(scenario_runs),
        "regression_rate": sum(float(row["regression_count"]) for row in scenario_runs) / len(scenario_runs),
        "carry_forward_integrity": sum(float(row["carry_forward_integrity"]) for row in scenario_runs) / len(scenario_runs),
        "median_round_latency_ms": float(median(float(row["median_round_latency_ms"]) for row in scenario_runs)),
        "median_round_active_context_size_bytes": float(
            median(float(row["median_round_active_context_size_bytes"]) for row in scenario_runs)
        ),
        "median_round_active_context_size_tokens": float(
            median(token_samples)
        ) if token_samples else None,
    }


def build_primary_budget_aggregate(
    pair_budget_rows: list[dict[str, Any]],
    *,
    locked_budget: int,
    continuity_mode: str,
) -> dict[str, Any]:
    if not pair_budget_rows:
        raise ValueError("build_primary_budget_aggregate requires at least one pair-budget row.")

    token_samples = [
        float(row["median_round_active_context_size_tokens"])
        for row in pair_budget_rows
        if row.get("median_round_active_context_size_tokens") is not None
    ]

    return {
        "locked_budget": int(locked_budget),
        "continuity_mode": str(continuity_mode),
        "pair_count": len(pair_budget_rows),
        "convergence_rate": sum(float(row["convergence_rate"]) for row in pair_budget_rows) / len(pair_budget_rows),
        "reopened_decision_rate": sum(float(row["reopened_decision_rate"]) for row in pair_budget_rows) / len(pair_budget_rows),
        "contradiction_rate": sum(float(row["contradiction_rate"]) for row in pair_budget_rows) / len(pair_budget_rows),
        "regression_rate": sum(float(row["regression_rate"]) for row in pair_budget_rows) / len(pair_budget_rows),
        "carry_forward_integrity": sum(float(row["carry_forward_integrity"]) for row in pair_budget_rows) / len(pair_budget_rows),
        "median_round_latency_ms": sum(float(row["median_round_latency_ms"]) for row in pair_budget_rows) / len(pair_budget_rows),
        "median_round_active_context_size_bytes": sum(
            float(row["median_round_active_context_size_bytes"]) for row in pair_budget_rows
        ) / len(pair_budget_rows),
        "median_round_active_context_size_tokens": sum(
            token_samples
        ) / len(token_samples) if token_samples else None,
    }


def resolve_lane_artifact_path(config: dict[str, Any], artifact_key: str) -> Path:
    artifact_paths = dict(config.get("artifact_paths") or {})
    raw = str(artifact_paths.get(artifact_key) or "").strip()
    if not raw:
        raise KeyError(f"Lane config artifact_paths missing {artifact_key}.")
    return (REPO_ROOT / raw).resolve()


def resolve_default_output_path(config: dict[str, Any]) -> Path:
    return resolve_lane_artifact_path(config, "bootstrap_summary")


def build_bootstrap_payload(config: dict[str, Any]) -> dict[str, Any]:
    prereg = load_pair_preregistration(config)
    output_schema = load_output_schema(config)
    v0_replay_contract = load_v0_replay_contract(config)
    v1_state_contract = load_v1_state_contract(config)
    continuity_mode_registry = build_continuity_mode_registry(config)
    primary_pairs = [pair.as_dict() for pair in config["selected_primary_pairs"]]
    secondary_pairs = [pair.as_dict() for pair in config["secondary_sensitivity_pairs"]]

    planned_pair_budget_runs: list[dict[str, Any]] = []
    for budget in config["locked_budgets"]:
        for mode in config["continuity_modes"]:
            for pair in config["selected_primary_pairs"]:
                planned_pair_budget_runs.append(
                    {
                        "pair_id": pair.pair_id,
                        "locked_budget": int(budget),
                        "continuity_mode": str(mode),
                        "scenario_ids": list(config["scenario_set"]["scenario_ids"]),
                        "scenario_run_count": len(config["scenario_set"]["scenario_ids"]),
                        "pair_scope": str(config["pair_scope"]),
                    }
                )

    return {
        "schema_version": "odr.context_continuity.bootstrap.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "lane_config_snapshot": {
            "config_path": str(config["config_path"]),
            "requirements_authority": str(config["requirements_authority"]),
            "implementation_authority": str(config["implementation_authority"]),
            "v0_replay_contract_path": str(config["v0_replay_contract_path"]),
            "v1_state_contract_path": str(config["v1_state_contract_path"]),
            "continuity_modes": list(config["continuity_modes"]),
            "locked_budgets": list(config["locked_budgets"]),
            "pair_scope": str(config["pair_scope"]),
            "scenario_set": dict(config["scenario_set"]),
            "artifact_paths": dict(config["artifact_paths"]),
            "control_freeze": dict(config["control_freeze"]),
            "decision_thresholds": dict(config.get("decision_thresholds") or {}),
        },
        "pre_registration_snapshot": {
            "path": str(config["pre_registration_record_path"]),
            "matrix_scope": str(prereg.get("matrix_scope") or ""),
            "selected_primary_pairs": list(prereg.get("selected_primary_pairs") or []),
            "secondary_sensitivity_pairs": list(prereg.get("secondary_sensitivity_pairs") or []),
            "excluded_pairs": list(prereg.get("excluded_pairs") or []),
        },
        "output_schema_snapshot": {
            "path": str(config["output_schema_path"]),
            "schema_version": str(output_schema.get("schema_version") or ""),
            "top_level_required": list(output_schema.get("top_level_required") or []),
            "inspectability_top_level_required": list(output_schema.get("inspectability_top_level_required") or []),
        },
        "v0_replay_contract_snapshot": {
            "path": str(config["v0_replay_contract_path"]),
            "schema_version": str(v0_replay_contract.get("schema_version") or ""),
            "allowed_source_kinds": list(v0_replay_contract.get("allowed_source_kinds") or []),
            "excluded_source_kinds": list(v0_replay_contract.get("excluded_source_kinds") or []),
        },
        "v1_state_contract_snapshot": {
            "path": str(config["v1_state_contract_path"]),
            "schema_version": str(v1_state_contract.get("schema_version") or ""),
            "allowed_item_states": list(v1_state_contract.get("allowed_item_states") or []),
            "identity_evidence_allowed": list(
                ((v1_state_contract.get("identity_evidence_rules") or {}).get("allowed") or [])
            ),
        },
        "execution_scope": {
            "evidence_scope": str(prereg.get("matrix_scope") or config["pair_scope"]),
            "selected_primary_pairs": primary_pairs,
            "secondary_sensitivity_pairs": secondary_pairs,
            "scenario_ids": list(config["scenario_set"]["scenario_ids"]),
            "locked_budgets": list(config["locked_budgets"]),
            "continuity_modes": list(config["continuity_modes"]),
        },
        "continuity_mode_registry": continuity_mode_registry,
        "control_mode_isolation": {
            "mode": "control_current_replay",
            "state_inputs_required": list(config["mode_state_inputs"]["control_current_replay"]),
            "reads_v0_or_v1_state": False,
        },
        "aggregation_contract": {
            "primary_unit": "scenario-run",
            "pair_budget_aggregate_keys": [
                "convergence_rate",
                "reopened_decision_rate",
                "contradiction_rate",
                "regression_rate",
                "carry_forward_integrity",
                "median_round_latency_ms",
                "median_round_active_context_size_tokens",
            ],
            "pair_equal_budget_aggregate_rule": "arithmetic mean across pair-budget aggregates",
        },
        "planned_pair_budget_runs": planned_pair_budget_runs,
        "canonical_output_paths": dict(config["artifact_paths"]),
    }
