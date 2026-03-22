from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.odr.context_continuity_live_proof import _call_role, run_live_scenario_mode
from scripts.odr.model_role_fit_compare import (
    build_closeout_payload,
    build_pair_compare_payload,
    build_pair_verdict_payload,
    build_triple_compare_payload,
    build_triple_verdict_payload,
)
from scripts.odr.model_role_fit_lane import (
    build_lane_bootstrap_payload,
    load_lane_config,
    load_matrix_registry,
    load_output_schema,
    resolve_lane_artifact_path,
)
from scripts.odr.model_role_fit_runtime_artifacts import (
    completed_entity_ids,
    existing_scenario_rows,
    inventory_status_map,
    load_existing_payload,
    runtime_blocker_rows,
)
from scripts.odr.model_role_fit_triple_runtime import admitted_triples, run_live_triple_scenario
from scripts.odr.run_odr_single_vs_coordinated import _load_scenario_inputs, _load_scenarios


def _inspectability_payload(
    *,
    config: dict[str, Any],
    phase: str,
    scenario_runs: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": f"odr.model_role_fit.{phase}_inspectability.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "phase": phase,
        "continuity_mode": str(config["continuity_mode"]),
        "scenario_set": dict(config["scenario_set"]),
        "lane_config_snapshot": {
            "config_path": str(config["config_path"]),
            "requirements_authority": str(config["requirements_authority"]),
            "implementation_authority": str(config["implementation_authority"]),
            "continuity_mode": str(config["continuity_mode"]),
            "locked_budgets": list(config["locked_budgets"]),
            "scenario_set": dict(config["scenario_set"]),
        },
        "scenario_run_artifacts": scenario_runs,
    }


def _pair_compare_row(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity_id": str(raw["pair_id"]),
        "pair_id": str(raw["pair_id"]),
        "scenario_id": str(raw["scenario_id"]),
        "locked_budget": int(raw["locked_budget"]),
        "execution_status": "success",
        "converged": bool(raw["converged"]),
        "stop_reason": str(raw["stop_reason"]),
        "rounds_consumed": int(raw["rounds_consumed"]),
        "reopened_decision_count": int(raw["reopened_decision_count"]),
        "contradiction_count": int(raw["contradiction_count"]),
        "regression_count": int(raw["regression_count"]),
        "carry_forward_integrity": float(raw["carry_forward_integrity"]),
        "round_latency_ms": list(raw["round_latency_ms"]),
        "round_active_context_size_bytes": list(raw["round_active_context_size_bytes"]),
        "round_active_context_size_tokens": list(raw["round_active_context_size_tokens"]),
    }


def _inventory_rows(registry: dict[str, Any]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    rows: list[dict[str, Any]] = []
    for row in list((registry.get("inventory_freeze") or {}).get("provider_models") or []):
        model_id = str(row.get("model_id") or "").strip()
        provider = str(row.get("provider") or "").strip()
        token = (model_id, provider)
        if token in seen:
            continue
        seen.add(token)
        rows.append({"model_id": model_id, "provider": provider, "status": "pending"})
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

def _persist_pair_artifacts(
    *,
    config: dict[str, Any],
    registry: dict[str, Any],
    inspect_rows: list[dict[str, Any]],
    compare_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    write_payload_with_diff_ledger(
        resolve_lane_artifact_path(config, "pair_inspectability_output"),
        _inspectability_payload(config=config, phase="pair", scenario_runs=inspect_rows),
    )
    pair_compare_payload = build_pair_compare_payload(config=config, registry=registry, raw_rows=compare_rows)
    write_payload_with_diff_ledger(resolve_lane_artifact_path(config, "pair_compare_output"), pair_compare_payload)
    pair_verdict_payload = build_pair_verdict_payload(
        config=config,
        registry=registry,
        pair_compare_payload=pair_compare_payload,
    )
    write_payload_with_diff_ledger(resolve_lane_artifact_path(config, "pair_verdict_output"), pair_verdict_payload)
    return pair_compare_payload, pair_verdict_payload


def _persist_triple_artifacts(
    *,
    config: dict[str, Any],
    inspect_rows: list[dict[str, Any]],
    compare_rows: list[dict[str, Any]],
    admitted: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    write_payload_with_diff_ledger(
        resolve_lane_artifact_path(config, "triple_inspectability_output"),
        _inspectability_payload(config=config, phase="triple", scenario_runs=inspect_rows),
    )
    triple_compare_payload = build_triple_compare_payload(config=config, raw_rows=compare_rows)
    write_payload_with_diff_ledger(resolve_lane_artifact_path(config, "triple_compare_output"), triple_compare_payload)
    triple_verdict_payload = build_triple_verdict_payload(
        triple_compare_payload=triple_compare_payload,
        admitted_triples=admitted,
    )
    triple_verdict_payload["skipped_triples"] = skipped
    write_payload_with_diff_ledger(resolve_lane_artifact_path(config, "triple_verdict_output"), triple_verdict_payload)
    return triple_compare_payload, triple_verdict_payload


async def run_model_role_fit_live_proof(*, config_path: Path | None = None) -> dict[str, Any]:
    config = load_lane_config(config_path)
    registry = load_matrix_registry(config)
    output_schema = load_output_schema(config)
    inventory_rows = await _preflight_inventory(registry, role_timeout_sec=int(config["role_timeout_sec"]))

    bootstrap_output = resolve_lane_artifact_path(config, "bootstrap_output")
    bootstrap_payload = build_lane_bootstrap_payload(config, registry, inventory_rows=inventory_rows)
    bootstrap_payload["output_schema_snapshot"] = {
        "path": str(config["output_schema_path"]),
        "schema_version": str(output_schema.get("schema_version") or ""),
        "required_artifacts": list(output_schema.get("required_artifacts") or []),
    }
    bootstrap_persisted = write_payload_with_diff_ledger(bootstrap_output, bootstrap_payload)
    inventory_status = inventory_status_map(inventory_rows)

    scenario_index = {str(row["id"]): row for row in _load_scenarios()}
    scenario_inputs = [_load_scenario_inputs(scenario_index[scenario_id]) for scenario_id in config["scenario_set"]["scenario_ids"]]
    pair_inspect_output = resolve_lane_artifact_path(config, "pair_inspectability_output")
    pair_compare_output = resolve_lane_artifact_path(config, "pair_compare_output")
    pair_verdict_output = resolve_lane_artifact_path(config, "pair_verdict_output")
    triple_inspect_output = resolve_lane_artifact_path(config, "triple_inspectability_output")
    triple_compare_output = resolve_lane_artifact_path(config, "triple_compare_output")
    triple_verdict_output = resolve_lane_artifact_path(config, "triple_verdict_output")

    pair_inspect_rows = existing_scenario_rows(load_existing_payload(pair_inspect_output), "scenario_run_artifacts")
    pair_compare_rows = existing_scenario_rows(load_existing_payload(pair_compare_output), "scenario_runs")
    pair_compare_payload: dict[str, Any] | None = None
    pair_verdict_payload: dict[str, Any] | None = None
    scenario_config = {
        "config_path": str(config["config_path"]),
        "v1_state_contract_path": str(config["reused_v1_state_contract_path"]),
        "role_timeout_sec": int(config["role_timeout_sec"]),
        "protocol_hardening": dict(config.get("protocol_hardening") or {}),
    }
    completed_pair_ids = completed_entity_ids(
        pair_compare_rows,
        scenario_count=len(scenario_inputs),
        budget_count=len(config["locked_budgets"]),
    )
    for pair in registry["primary_pairs"]:
        if pair.pair_id in completed_pair_ids:
            continue
        pair_preflight_error = next(
            (
                str(row.get("error") or "inventory_preflight_error")
                for row in (
                    inventory_status.get((pair.architect_model, pair.architect_provider)),
                    inventory_status.get((pair.reviewer_model, pair.reviewer_provider)),
                )
                if isinstance(row, dict) and str(row.get("status") or "") != "ok"
            ),
            None,
        )
        if pair_preflight_error is not None:
            blocked_inspect, blocked_compare = runtime_blocker_rows(
                entity_id=pair.pair_id,
                scenario_inputs=scenario_inputs,
                locked_budgets=list(config["locked_budgets"]),
                error=RuntimeError(pair_preflight_error),
            )
            pair_inspect_rows.extend(blocked_inspect)
            pair_compare_rows.extend(blocked_compare)
            pair_compare_payload, pair_verdict_payload = _persist_pair_artifacts(
                config=config,
                registry=registry,
                inspect_rows=pair_inspect_rows,
                compare_rows=pair_compare_rows,
            )
            continue
        try:
            for locked_budget in config["locked_budgets"]:
                for scenario_input in scenario_inputs:
                    inspect_row, compare_row = await run_live_scenario_mode(
                        config=scenario_config,
                        pair=pair,
                        scenario_input=scenario_input,
                        continuity_mode="v1_compiled_shared_state",
                        locked_budget=int(locked_budget),
                    )
                    pair_inspect_rows.append(inspect_row)
                    pair_compare_rows.append(_pair_compare_row(compare_row))
        except Exception as exc:  # noqa: BLE001
            blocked_inspect, blocked_compare = runtime_blocker_rows(
                entity_id=pair.pair_id,
                scenario_inputs=scenario_inputs,
                locked_budgets=list(config["locked_budgets"]),
                error=exc,
            )
            pair_inspect_rows.extend(blocked_inspect)
            pair_compare_rows.extend(blocked_compare)
        pair_compare_payload, pair_verdict_payload = _persist_pair_artifacts(
            config=config,
            registry=registry,
            inspect_rows=pair_inspect_rows,
            compare_rows=pair_compare_rows,
        )

    if pair_compare_payload is None or pair_verdict_payload is None:
        pair_compare_payload, pair_verdict_payload = _persist_pair_artifacts(
            config=config,
            registry=registry,
            inspect_rows=pair_inspect_rows,
            compare_rows=pair_compare_rows,
        )

    admitted, skipped = admitted_triples(
        registry,
        selected_pair_ids=list(pair_verdict_payload["selected_pairs_for_triples"]),
    )
    triple_inspect_rows = existing_scenario_rows(load_existing_payload(triple_inspect_output), "scenario_run_artifacts")
    triple_compare_rows = existing_scenario_rows(load_existing_payload(triple_compare_output), "scenario_runs")
    triple_compare_payload: dict[str, Any] | None = None
    triple_verdict_payload: dict[str, Any] | None = None
    completed_triple_ids = completed_entity_ids(
        triple_compare_rows,
        scenario_count=len(scenario_inputs),
        budget_count=len(config["locked_budgets"]),
    )
    for triple_variant in admitted:
        if str(triple_variant["triple_id"]) in completed_triple_ids:
            continue
        triple_inventory_rows = [
            inventory_status.get((str(triple_variant["architect_model"]), str(triple_variant["architect_provider"]))),
            *[
                inventory_status.get((str(reviewer["model"]), str(reviewer["provider"])))
                for reviewer in list(triple_variant["reviewer_order"])
            ],
        ]
        triple_preflight_error = next(
            (
                str(row.get("error") or "inventory_preflight_error")
                for row in triple_inventory_rows
                if isinstance(row, dict) and str(row.get("status") or "") != "ok"
            ),
            None,
        )
        if triple_preflight_error is not None:
            blocked_inspect, blocked_compare = runtime_blocker_rows(
                entity_id=str(triple_variant["triple_id"]),
                scenario_inputs=scenario_inputs,
                locked_budgets=list(config["locked_budgets"]),
                error=RuntimeError(triple_preflight_error),
                triple_variant=triple_variant,
            )
            triple_inspect_rows.extend(blocked_inspect)
            triple_compare_rows.extend(blocked_compare)
            triple_compare_payload, triple_verdict_payload = _persist_triple_artifacts(
                config=config,
                inspect_rows=triple_inspect_rows,
                compare_rows=triple_compare_rows,
                admitted=admitted,
                skipped=skipped,
            )
            continue
        try:
            for locked_budget in config["locked_budgets"]:
                for scenario_input in scenario_inputs:
                    inspect_row, compare_row = await run_live_triple_scenario(
                        config=config,
                        triple_variant=triple_variant,
                        scenario_input=scenario_input,
                        locked_budget=int(locked_budget),
                    )
                    triple_inspect_rows.append(inspect_row)
                    triple_compare_rows.append(compare_row)
        except Exception as exc:  # noqa: BLE001
            blocked_inspect, blocked_compare = runtime_blocker_rows(
                entity_id=str(triple_variant["triple_id"]),
                scenario_inputs=scenario_inputs,
                locked_budgets=list(config["locked_budgets"]),
                error=exc,
                triple_variant=triple_variant,
            )
            triple_inspect_rows.extend(blocked_inspect)
            triple_compare_rows.extend(blocked_compare)
        triple_compare_payload, triple_verdict_payload = _persist_triple_artifacts(
            config=config,
            inspect_rows=triple_inspect_rows,
            compare_rows=triple_compare_rows,
            admitted=admitted,
            skipped=skipped,
        )

    if triple_compare_payload is None or triple_verdict_payload is None:
        triple_compare_payload, triple_verdict_payload = _persist_triple_artifacts(
            config=config,
            inspect_rows=triple_inspect_rows,
            compare_rows=triple_compare_rows,
            admitted=admitted,
            skipped=skipped,
        )

    closeout_output = resolve_lane_artifact_path(config, "closeout_output")
    closeout_payload = build_closeout_payload(
        config=config,
        registry=registry,
        pair_compare_payload=pair_compare_payload,
        pair_verdict_payload=pair_verdict_payload,
        triple_compare_payload=triple_compare_payload,
        triple_verdict_payload=triple_verdict_payload,
        skipped_triples=skipped,
    )
    closeout_persisted = write_payload_with_diff_ledger(closeout_output, closeout_payload)
    return {
        "bootstrap_output": str(bootstrap_output),
        "pair_inspectability_output": str(pair_inspect_output),
        "pair_compare_output": str(pair_compare_output),
        "pair_verdict_output": str(pair_verdict_output),
        "triple_inspectability_output": str(triple_inspect_output),
        "triple_compare_output": str(triple_compare_output),
        "triple_verdict_output": str(triple_verdict_output),
        "closeout_output": str(closeout_output),
        "bootstrap_payload": bootstrap_persisted,
        "pair_compare_payload": pair_compare_payload,
        "pair_verdict_payload": pair_verdict_payload,
        "triple_compare_payload": triple_compare_payload,
        "triple_verdict_payload": triple_verdict_payload,
        "closeout_payload": closeout_persisted,
    }
