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
    / "ODRModelRoleFit"
    / "MRF03212026"
    / "odr_model_role_fit_lane_config.json"
)
REQUIRED_ARTIFACT_PATH_KEYS = (
    "root",
    "bootstrap_output",
    "pair_inspectability_output",
    "pair_compare_output",
    "pair_verdict_output",
    "triple_inspectability_output",
    "triple_compare_output",
    "triple_verdict_output",
    "closeout_output",
)
DEFAULT_ROLE_TIMEOUT_SEC = 120


@dataclass(frozen=True)
class PairSpec:
    pair_id: str
    architect_model: str
    architect_provider: str
    reviewer_model: str
    reviewer_provider: str
    execution_order: int

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PairSpec":
        return cls(
            pair_id=str(raw["pair_id"]),
            architect_model=str(raw["architect_model"]),
            architect_provider=str(raw["architect_provider"]),
            reviewer_model=str(raw["reviewer_model"]),
            reviewer_provider=str(raw["reviewer_provider"]),
            execution_order=int(raw["execution_order"]),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "pair_id": self.pair_id,
            "architect_model": self.architect_model,
            "architect_provider": self.architect_provider,
            "reviewer_model": self.reviewer_model,
            "reviewer_provider": self.reviewer_provider,
            "execution_order": self.execution_order,
        }

    @property
    def auditor_model(self) -> str:
        return self.reviewer_model

    @property
    def auditor_provider(self) -> str:
        return self.reviewer_provider


@dataclass(frozen=True)
class TripleSpec:
    triple_id: str
    architect_model: str
    architect_provider: str
    reviewer_a_model: str
    reviewer_a_provider: str
    reviewer_b_model: str
    reviewer_b_provider: str
    base_execution_order: int

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "TripleSpec":
        return cls(
            triple_id=str(raw["triple_id"]),
            architect_model=str(raw["architect_model"]),
            architect_provider=str(raw["architect_provider"]),
            reviewer_a_model=str(raw["reviewer_a_model"]),
            reviewer_a_provider=str(raw["reviewer_a_provider"]),
            reviewer_b_model=str(raw["reviewer_b_model"]),
            reviewer_b_provider=str(raw["reviewer_b_provider"]),
            base_execution_order=int(raw["base_execution_order"]),
        )

    def ordered_variants(self) -> list[dict[str, Any]]:
        return [
            {
                "triple_id": f"{self.triple_id}__a_then_b",
                "base_triple_id": self.triple_id,
                "architect_model": self.architect_model,
                "architect_provider": self.architect_provider,
                "reviewer_order": [
                    {"role": "reviewer_a", "model": self.reviewer_a_model, "provider": self.reviewer_a_provider},
                    {"role": "reviewer_b", "model": self.reviewer_b_model, "provider": self.reviewer_b_provider},
                ],
                "execution_order": self.base_execution_order * 2 - 1,
            },
            {
                "triple_id": f"{self.triple_id}__b_then_a",
                "base_triple_id": self.triple_id,
                "architect_model": self.architect_model,
                "architect_provider": self.architect_provider,
                "reviewer_order": [
                    {"role": "reviewer_b", "model": self.reviewer_b_model, "provider": self.reviewer_b_provider},
                    {"role": "reviewer_a", "model": self.reviewer_a_model, "provider": self.reviewer_a_provider},
                ],
                "execution_order": self.base_execution_order * 2,
            },
        ]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_path(config_path: Path, raw: str) -> Path:
    candidate = Path(str(raw or "").strip())
    if not candidate.is_absolute():
        candidate = config_path.parent / candidate
    return candidate.resolve()


def load_lane_config(path: Path | None = None) -> dict[str, Any]:
    config_path = (path or DEFAULT_LANE_CONFIG_PATH).resolve()
    payload = _read_json(config_path)
    payload["config_path"] = str(config_path)

    continuity_mode = str(payload.get("continuity_mode") or "").strip()
    if continuity_mode != "v1_compiled_shared_state":
        raise ValueError("Model-role fit lane must freeze continuity_mode=v1_compiled_shared_state.")

    locked_budgets = [int(item) for item in list(payload.get("locked_budgets") or [])]
    if not locked_budgets or any(item <= 0 for item in locked_budgets):
        raise ValueError("Lane config must declare positive locked_budgets.")
    payload["locked_budgets"] = locked_budgets

    scenario_ids = [str(item).strip() for item in list((payload.get("scenario_set") or {}).get("scenario_ids") or [])]
    if not scenario_ids:
        raise ValueError("Lane config must declare a non-empty scenario_set.scenario_ids list.")

    artifact_paths = dict(payload.get("artifact_paths") or {})
    for key in REQUIRED_ARTIFACT_PATH_KEYS:
        if not str(artifact_paths.get(key) or "").strip():
            raise ValueError(f"Lane config artifact_paths missing {key}.")
    payload["artifact_paths"] = artifact_paths

    for key in ("matrix_registry", "output_schema", "reused_v1_state_contract", "reused_continuity_closeout"):
        raw = str(payload.get(key) or "").strip()
        if not raw:
            raise ValueError(f"Lane config missing {key}.")
        resolved = _resolve_path(config_path, raw)
        if not resolved.exists():
            raise FileNotFoundError(f"Lane config dependency not found: {resolved}")
        payload[f"{key}_path"] = str(resolved)

    structural = dict(payload.get("structural_disqualification") or {})
    stop_reasons = [str(item).strip() for item in list(structural.get("stop_reasons") or []) if str(item).strip()]
    if not stop_reasons:
        raise ValueError("Lane config must declare structural_disqualification.stop_reasons.")
    payload["structural_disqualification"] = {
        "stop_reasons": stop_reasons,
        "max_failure_rate": float(structural.get("max_failure_rate")),
    }
    if not (0.0 <= float(payload["structural_disqualification"]["max_failure_rate"]) <= 1.0):
        raise ValueError("structural_disqualification.max_failure_rate must be between 0 and 1.")

    top_pair_count = int(payload.get("top_pair_count_for_triples") or 0)
    if top_pair_count <= 0:
        raise ValueError("Lane config must declare positive top_pair_count_for_triples.")
    payload["top_pair_count_for_triples"] = top_pair_count

    role_timeout_sec = int(payload.get("role_timeout_sec") or DEFAULT_ROLE_TIMEOUT_SEC)
    if role_timeout_sec <= 0:
        raise ValueError("Lane config role_timeout_sec must be positive.")
    payload["role_timeout_sec"] = role_timeout_sec
    return payload


def load_matrix_registry(config: dict[str, Any]) -> dict[str, Any]:
    payload = _read_json(Path(str(config["matrix_registry_path"])))
    pairs = sorted(
        [PairSpec.from_dict(row) for row in list(payload.get("primary_pairs") or [])],
        key=lambda row: row.execution_order,
    )
    triples = sorted(
        [TripleSpec.from_dict(row) for row in list(payload.get("preferred_triples") or [])],
        key=lambda row: row.base_execution_order,
    )
    if not pairs:
        raise ValueError("Matrix registry must declare primary_pairs.")
    payload["primary_pairs"] = pairs
    payload["preferred_triples"] = triples
    return payload


def load_output_schema(config: dict[str, Any]) -> dict[str, Any]:
    return _read_json(Path(str(config["output_schema_path"])))


def resolve_lane_artifact_path(config: dict[str, Any], artifact_key: str) -> Path:
    raw = str((config.get("artifact_paths") or {}).get(artifact_key) or "").strip()
    if not raw:
        raise KeyError(f"Lane config artifact_paths missing {artifact_key}.")
    return (REPO_ROOT / raw).resolve()


def build_entity_budget_aggregate(
    scenario_runs: list[dict[str, Any]],
    *,
    entity_id: str,
    locked_budget: int,
) -> dict[str, Any]:
    if not scenario_runs:
        raise ValueError("build_entity_budget_aggregate requires at least one scenario-run.")
    token_samples = [
        float(row["median_round_active_context_size_tokens"])
        for row in scenario_runs
        if row.get("median_round_active_context_size_tokens") is not None
    ]
    return {
        "entity_id": entity_id,
        "locked_budget": int(locked_budget),
        "scenario_run_count": len(scenario_runs),
        "execution_blocker_rate": sum(
            1.0 if str(row.get("execution_status") or "success") != "success" else 0.0 for row in scenario_runs
        ) / len(scenario_runs),
        "convergence_rate": sum(1.0 if bool(row["converged"]) else 0.0 for row in scenario_runs) / len(scenario_runs),
        "reopened_decision_rate": sum(float(row["reopened_decision_count"]) for row in scenario_runs) / len(scenario_runs),
        "contradiction_rate": sum(float(row["contradiction_count"]) for row in scenario_runs) / len(scenario_runs),
        "regression_rate": sum(float(row["regression_count"]) for row in scenario_runs) / len(scenario_runs),
        "carry_forward_integrity": sum(float(row["carry_forward_integrity"]) for row in scenario_runs) / len(scenario_runs),
        "median_round_latency_ms": float(median(float(row["median_round_latency_ms"]) for row in scenario_runs)),
        "median_round_active_context_size_bytes": float(
            median(float(row["median_round_active_context_size_bytes"]) for row in scenario_runs)
        ),
        "median_round_active_context_size_tokens": float(median(token_samples)) if token_samples else None,
        "structural_failure_rate": sum(
            1.0 if bool(row.get("structural_failure")) else 0.0 for row in scenario_runs
        ) / len(scenario_runs),
    }


def build_entity_summary_aggregate(
    scenario_runs: list[dict[str, Any]],
    *,
    entity_id: str,
) -> dict[str, Any]:
    if not scenario_runs:
        raise ValueError("build_entity_summary_aggregate requires at least one scenario-run.")
    token_samples = [
        float(row["median_round_active_context_size_tokens"])
        for row in scenario_runs
        if row.get("median_round_active_context_size_tokens") is not None
    ]
    stop_reason_distribution: dict[str, int] = {}
    for row in scenario_runs:
        stop_reason = str(row.get("stop_reason") or "NONE")
        stop_reason_distribution[stop_reason] = int(stop_reason_distribution.get(stop_reason, 0)) + 1
    return {
        "entity_id": entity_id,
        "scenario_run_count": len(scenario_runs),
        "execution_blocker_rate": sum(
            1.0 if str(row.get("execution_status") or "success") != "success" else 0.0 for row in scenario_runs
        ) / len(scenario_runs),
        "convergence_rate": sum(1.0 if bool(row["converged"]) else 0.0 for row in scenario_runs) / len(scenario_runs),
        "reopened_decision_rate": sum(float(row["reopened_decision_count"]) for row in scenario_runs) / len(scenario_runs),
        "contradiction_rate": sum(float(row["contradiction_count"]) for row in scenario_runs) / len(scenario_runs),
        "regression_rate": sum(float(row["regression_count"]) for row in scenario_runs) / len(scenario_runs),
        "carry_forward_integrity": sum(float(row["carry_forward_integrity"]) for row in scenario_runs) / len(scenario_runs),
        "median_round_latency_ms": float(median(float(row["median_round_latency_ms"]) for row in scenario_runs)),
        "median_round_active_context_size_bytes": float(
            median(float(row["median_round_active_context_size_bytes"]) for row in scenario_runs)
        ),
        "median_round_active_context_size_tokens": float(median(token_samples)) if token_samples else None,
        "structural_failure_rate": sum(
            1.0 if bool(row.get("structural_failure")) else 0.0 for row in scenario_runs
        ) / len(scenario_runs),
        "stop_reason_distribution": stop_reason_distribution,
    }


def build_lane_bootstrap_payload(
    config: dict[str, Any],
    registry: dict[str, Any],
    *,
    inventory_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": "odr.model_role_fit.bootstrap.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "lane_config_snapshot": {
            "config_path": str(config["config_path"]),
            "requirements_authority": str(config["requirements_authority"]),
            "implementation_authority": str(config["implementation_authority"]),
            "continuity_mode": str(config["continuity_mode"]),
            "locked_budgets": list(config["locked_budgets"]),
            "scenario_set": dict(config["scenario_set"]),
            "artifact_paths": dict(config["artifact_paths"]),
            "structural_disqualification": dict(config["structural_disqualification"]),
            "top_pair_count_for_triples": int(config["top_pair_count_for_triples"]),
            "role_timeout_sec": int(config["role_timeout_sec"]),
            "protocol_hardening": dict(config.get("protocol_hardening") or {}),
        },
        "matrix_registry_snapshot": {
            "path": str(config["matrix_registry_path"]),
            "primary_pairs": [pair.as_dict() for pair in registry["primary_pairs"]],
            "preferred_triples": [
                {
                    "triple_id": triple.triple_id,
                    "architect_model": triple.architect_model,
                    "reviewer_a_model": triple.reviewer_a_model,
                    "reviewer_b_model": triple.reviewer_b_model,
                    "base_execution_order": triple.base_execution_order,
                }
                for triple in registry["preferred_triples"]
            ],
        },
        "inventory_preflight": inventory_rows,
    }
