from __future__ import annotations

from pathlib import Path
from typing import Any

from orket.kernel.v1.odr.core import ReactorConfig, ReactorState, run_round
from orket.kernel.v1.odr.prompt_contract import build_auditor_messages
from scripts.odr.context_continuity_live_proof import (
    CONVERGED_STOP_REASONS,
    _call_role,
    _prepare_round_context,
    _prompt_bytes,
    _why_loaded_context_changed,
    auditor_user_content,
)
from scripts.odr.context_continuity_live_v1 import build_v1_post_round_state
from scripts.odr.context_continuity_v1_state import compute_v1_continuity_run_metrics
from scripts.odr.model_role_fit_lane import PairSpec, TripleSpec
from scripts.odr.run_odr_single_vs_coordinated import _scenario_brief


def _continuity_config(config: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(config)
    contract_path = str(
        normalized.get("v1_state_contract_path") or normalized.get("reused_v1_state_contract_path") or ""
    ).strip()
    if not contract_path:
        raise KeyError("v1_state_contract_path")
    normalized["v1_state_contract_path"] = contract_path
    return normalized


def admitted_triples(
    registry: dict[str, Any],
    *,
    selected_pair_ids: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if len(selected_pair_ids) < 2:
        return [], [{"reason": "insufficient_surviving_pairs", "selected_pair_ids": list(selected_pair_ids)}]
    pair_lookup = {pair.pair_id: pair for pair in registry["primary_pairs"]}
    surviving_models = {
        pair_lookup[pair_id].architect_model
        for pair_id in selected_pair_ids
        if pair_id in pair_lookup
    } | {
        pair_lookup[pair_id].reviewer_model
        for pair_id in selected_pair_ids
        if pair_id in pair_lookup
    }
    admitted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for triple in registry["preferred_triples"]:
        required_models = {triple.architect_model, triple.reviewer_a_model, triple.reviewer_b_model}
        if not required_models.issubset(surviving_models):
            skipped.append(
                {
                    "triple_id": triple.triple_id,
                    "reason": "constituent_models_not_all_in_top_pairs",
                    "required_models": sorted(required_models),
                    "surviving_models": sorted(surviving_models),
                }
            )
            continue
        admitted.extend(triple.ordered_variants())
    admitted.sort(key=lambda row: int(row["execution_order"]))
    return admitted, skipped


def _max_prompt_tokens(values: list[int | None]) -> int | None:
    ints = [value for value in values if isinstance(value, int)]
    return max(ints) if ints else None


def _reviewer_role_view(reviewer_outputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "role": row["role"],
            "provider_request_token_count": row["prompt_tokens"],
            "loaded_context": row["loaded_context"],
            "provider": row["provider"],
            "model": row["model"],
        }
        for row in reviewer_outputs
    ]


async def run_live_triple_scenario(
    *,
    config: dict[str, Any],
    triple_variant: dict[str, Any],
    scenario_input: dict[str, Any],
    locked_budget: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    continuity_config = _continuity_config(config)
    role_timeout_sec = int(config.get("role_timeout_sec") or 120)
    task = _scenario_brief(scenario_input)
    current_requirement = str(scenario_input.get("R0") or "")
    prior_reviewer_output = ""
    latest_trace: dict[str, Any] | None = None
    state = ReactorState()
    cfg = ReactorConfig(max_rounds=int(locked_budget))
    round_rows: list[dict[str, Any]] = []
    inspect_rounds: list[dict[str, Any]] = []
    prior_v1_state_payload: dict[str, Any] | None = None
    v1_state_history: list[dict[str, Any]] = []
    for round_number in range(1, int(locked_budget) + 1):
        (
            source_inputs,
            continuity_context_by_role,
            mode_artifacts,
            architect_user,
            architect_messages,
            _role_focus_by_role,
        ) = _prepare_round_context(
            config=continuity_config,
            scenario_input=scenario_input,
            continuity_mode="v1_compiled_shared_state",
            round_number=round_number,
            task=task,
            current_requirement=current_requirement,
            prior_auditor_output=prior_reviewer_output,
            latest_trace=latest_trace,
            prior_v1_state_payload=prior_v1_state_payload,
        )
        architect_raw, _architect_payload, architect_latency_ms, architect_prompt_tokens = await _call_role(
            model=str(triple_variant["architect_model"]),
            provider_name=str(triple_variant["architect_provider"]),
            messages=architect_messages,
            timeout_sec=role_timeout_sec,
        )
        source_inputs.append(
            {
                "artifact_id": f"architect_output_r{round_number}",
                "artifact_kind": "latest_architect_delta",
                "authority_level": "authoritative",
                "content": architect_raw,
            }
        )

        reviewer_outputs: list[dict[str, Any]] = []
        prompt_sizes = [_prompt_bytes(architect_messages)]
        prompt_token_counts = [architect_prompt_tokens]
        total_latency_ms = architect_latency_ms
        prior_chain_text = ""
        for reviewer in list(triple_variant["reviewer_order"]):
            architect_material = architect_raw
            if prior_chain_text.strip():
                architect_material = f"{architect_raw}\n\nPrior reviewer critique:\n{prior_chain_text}"
            reviewer_user = auditor_user_content(
                task=task,
                architect_output=architect_material,
                continuity_context=continuity_context_by_role["auditor"],
            )
            reviewer_messages = [
                build_auditor_messages(task=task, architect_output=architect_material)[0],
                {"role": "user", "content": reviewer_user},
            ]
            reviewer_raw, _reviewer_payload, reviewer_latency_ms, reviewer_prompt_tokens = await _call_role(
                model=str(reviewer["model"]),
                provider_name=str(reviewer["provider"]),
                messages=reviewer_messages,
                timeout_sec=role_timeout_sec,
            )
            reviewer_outputs.append(
                {
                    "role": str(reviewer["role"]),
                    "model": str(reviewer["model"]),
                    "provider": str(reviewer["provider"]),
                    "output": reviewer_raw,
                    "loaded_context": reviewer_user,
                    "prompt_tokens": reviewer_prompt_tokens,
                }
            )
            source_inputs.append(
                {
                    "artifact_id": f"{reviewer['role']}_output_r{round_number}",
                    "artifact_kind": "reviewer_output",
                    "authority_level": "authoritative",
                    "content": reviewer_raw,
                }
            )
            prior_chain_text = f"{prior_chain_text}\n\n### {reviewer['role'].upper()}\n{reviewer_raw}".strip()
            total_latency_ms += reviewer_latency_ms
            prompt_sizes.append(_prompt_bytes(reviewer_messages))
            prompt_token_counts.append(reviewer_prompt_tokens)

        combined_reviewer_output = "\n\n".join(
            f"### {row['role'].upper()}\n{row['output']}" for row in reviewer_outputs
        )
        state = run_round(state, architect_raw, combined_reviewer_output, cfg)
        latest_trace = state.history_rounds[-1] if state.history_rounds else None
        round_rows.append(
            {
                "trace": latest_trace,
                "round_latency_ms": total_latency_ms,
                "round_active_context_size_bytes": max(prompt_sizes),
                "round_active_context_size_tokens": _max_prompt_tokens(prompt_token_counts),
            }
        )
        inspect_rounds.append(
            {
                "round_index": round_number - 1,
                "why_loaded_context_changed": _why_loaded_context_changed("v1_compiled_shared_state", round_number),
                "source_inputs": source_inputs,
                "mode_artifacts": mode_artifacts,
                "role_views": [
                    {
                        "role": "architect",
                        "provider_request_token_count": architect_prompt_tokens,
                        "loaded_context": architect_user,
                        "provider": str(triple_variant["architect_provider"]),
                        "model": str(triple_variant["architect_model"]),
                    },
                    *_reviewer_role_view(reviewer_outputs),
                ],
            }
        )
        if isinstance(latest_trace, dict) and str(latest_trace.get("validity_verdict") or "") == "valid":
            next_requirement = str((latest_trace.get("architect_parsed") or {}).get("requirement") or "").strip()
            if next_requirement:
                current_requirement = next_requirement
        prior_reviewer_output = combined_reviewer_output
        post_round_source_inputs = [
            {
                "artifact_id": str(item["artifact_id"]),
                "artifact_kind": str(item["artifact_kind"]),
                "content": item.get("content", item.get("artifact_body", "")),
            }
            for item in source_inputs
        ]
        post_round_state = build_v1_post_round_state(
            source_inputs=post_round_source_inputs,
            current_requirement=current_requirement,
            round_number=round_number,
            prior_state_payload=prior_v1_state_payload,
            latest_trace=latest_trace,
            v1_state_contract_path=Path(str(config["reused_v1_state_contract_path"])),
        )
        prior_v1_state_payload = dict(post_round_state["payload"])
        v1_state_history.append({"artifact_body": dict(post_round_state["payload"])})
        if state.stop_reason is not None:
            break

    compare_row = {
        "entity_id": str(triple_variant["triple_id"]),
        "base_triple_id": str(triple_variant["base_triple_id"]),
        "reviewer_order": [row["role"] for row in list(triple_variant["reviewer_order"])],
        "scenario_id": str(scenario_input["id"]),
        "locked_budget": int(locked_budget),
        "converged": str(state.stop_reason or "") in CONVERGED_STOP_REASONS,
        "stop_reason": str(state.stop_reason or "NONE"),
        "rounds_consumed": len(round_rows),
        **compute_v1_continuity_run_metrics(v1_state_history),
        "round_latency_ms": [row["round_latency_ms"] for row in round_rows],
        "round_active_context_size_bytes": [row["round_active_context_size_bytes"] for row in round_rows],
        "round_active_context_size_tokens": [
            row["round_active_context_size_tokens"]
            for row in round_rows
            if row["round_active_context_size_tokens"] is not None
        ],
    }
    inspect_row = {
        "entity_id": str(triple_variant["triple_id"]),
        "base_triple_id": str(triple_variant["base_triple_id"]),
        "reviewer_order": [row["role"] for row in list(triple_variant["reviewer_order"])],
        "scenario_id": str(scenario_input["id"]),
        "locked_budget": int(locked_budget),
        "rounds": inspect_rounds,
    }
    return inspect_row, compare_row
