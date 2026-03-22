from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from orket.kernel.v1.odr.core import ReactorConfig, ReactorState, run_round
from orket.kernel.v1.odr.prompt_contract import build_architect_messages, build_auditor_messages
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.odr.context_continuity_compare import (
    build_context_continuity_compare_payload_from_rows,
    resolve_default_compare_output_path,
)
from scripts.odr.context_continuity_inspectability import build_inspectability_payload
from scripts.odr.context_continuity_lane import load_lane_config, resolve_lane_artifact_path
from scripts.odr.context_continuity_live_metrics import (
    build_replay_source_history,
    compute_continuity_run_metrics,
)
from scripts.odr.context_continuity_live_v1 import (
    build_v1_post_round_state,
    build_v1_pre_round_state,
    initial_unresolved_source_inputs,
)
from scripts.odr.context_continuity_v0_replay import build_v0_replay_block
from scripts.odr.context_continuity_v1_state import compute_v1_continuity_run_metrics
from scripts.odr.context_continuity_verdict import (
    build_context_continuity_verdict_payload_from_payload,
    resolve_default_verdict_output_path,
)
from scripts.odr.model_runtime_control import complete_with_transient_provider
from scripts.odr.run_odr_single_vs_coordinated import (
    _load_scenario_inputs,
    _load_scenarios,
    _resolve_role_base_url,
    _resolve_role_provider,
    _scenario_brief,
)

CONVERGED_STOP_REASONS = {"STABLE_DIFF_FLOOR", "LOOP_DETECTED"}
V1_ARCHITECT_FOCUS = (
    "Use the compiled shared state as authoritative continuity context for refinement. "
    "Preserve accepted decisions unless an explicit supersession record is provided."
)
V1_AUDITOR_FOCUS = (
    "Use the compiled shared state as authoritative continuity context for critique. "
    "Challenge gaps without reopening accepted decisions unless an explicit supersession record is justified."
)


def _prompt_hardening_rules(config: dict[str, Any], *, role: str, round_number: int) -> list[str]:
    policy = config.get("protocol_hardening")
    if not isinstance(policy, dict):
        return []
    rows = [str(item).strip() for item in list(policy.get(f"{role}_extra_rules") or []) if str(item).strip()]
    conditional = policy.get(f"{role}_extra_rules_after_round")
    if isinstance(conditional, dict):
        threshold = int(conditional.get("round_number_gte") or 0)
        if int(round_number) >= threshold > 0:
            rows.extend(str(item).strip() for item in list(conditional.get("rules") or []) if str(item).strip())
    return rows


def _prompt_bytes(messages: list[dict[str, str]]) -> int:
    return len(json.dumps(messages, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def _prompt_tokens(response_raw: dict[str, Any]) -> int | None:
    value = response_raw.get("input_tokens")
    return int(value) if isinstance(value, int) else None


def _max_optional(left: int | None, right: int | None) -> int | None:
    values = [value for value in (left, right) if isinstance(value, int)]
    return max(values) if values else None


def architect_user_content(*, task: str, current_requirement: str, prior_auditor_output: str, continuity_context: str) -> str:
    if not continuity_context:
        return build_architect_messages(
            task=task,
            current_requirement=current_requirement,
            prior_auditor_output=prior_auditor_output,
        )[1]["content"]
    return (
        f"Task to refine:\n{task}\n\n"
        f"Continuity context:\n{continuity_context}\n\n"
        f"Current requirement draft:\n{current_requirement or '(none)'}\n\n"
        f"Prior auditor output:\n{prior_auditor_output or '(none)'}\n"
    )


def auditor_user_content(*, task: str, architect_output: str, continuity_context: str) -> str:
    if not continuity_context:
        return build_auditor_messages(task=task, architect_output=architect_output)[1]["content"]
    return (
        f"Original task:\n{task}\n\n"
        f"Continuity context:\n{continuity_context}\n\n"
        f"Architect output to audit:\n{architect_output}\n"
    )


def _provider_base_url(provider_name: str) -> str:
    return _resolve_role_base_url(provider=_resolve_role_provider(provider_name), raw="")


async def _call_role(
    *,
    model: str,
    provider_name: str,
    messages: list[dict[str, str]],
    timeout_sec: int = 120,
) -> tuple[str, dict[str, Any], int, int | None]:
    response, latency_ms, _release = await complete_with_transient_provider(
        model=model,
        messages=messages,
        temperature=0.1,
        timeout=int(timeout_sec),
        provider_name=provider_name,
        base_url=_provider_base_url(provider_name),
    )
    return str(response.content or "").strip(), response.raw, latency_ms, _prompt_tokens(response.raw)


def _base_source_inputs(
    *,
    round_number: int,
    scenario_input: dict[str, Any],
    task: str,
    current_requirement: str,
    prior_auditor_output: str,
) -> list[dict[str, Any]]:
    rows = [
        {"artifact_id": f"task_brief_r{round_number}", "artifact_kind": "task_brief", "content": task},
        {
            "artifact_id": f"current_requirement_r{round_number}",
            "artifact_kind": "current_canonical_artifact",
            "authority_level": "authoritative",
            "content": current_requirement,
        },
    ]
    if prior_auditor_output.strip():
        rows.append(
            {
                "artifact_id": f"prior_auditor_r{round_number}",
                "artifact_kind": "latest_auditor_critique",
                "authority_level": "authoritative",
                "content": prior_auditor_output,
            }
        )
    elif round_number == 1:
        rows.extend(initial_unresolved_source_inputs(scenario_input=scenario_input, round_number=round_number))
    return rows


def _continuity_context_bundle(
    *,
    continuity_mode: str,
    scenario_input: dict[str, Any],
    current_requirement: str,
    prior_auditor_output: str,
    latest_trace: dict[str, Any] | None,
    round_number: int,
    config_path: Path,
) -> tuple[str, dict[str, Any]]:
    if continuity_mode != "v0_log_derived_replay":
        return "", {}
    source_history = build_replay_source_history(
        scenario_input=scenario_input,
        current_requirement=current_requirement,
        prior_auditor_output=prior_auditor_output,
        latest_trace=latest_trace,
        round_index=round_number - 1,
    )
    replay_builder_input = {"artifact_id": f"v0_replay_r{round_number}", "source_history": source_history}
    replay_block = build_v0_replay_block(
        source_history,
        artifact_id=str(replay_builder_input["artifact_id"]),
        config_path=config_path,
    )
    return str(replay_block["content"]), {"replay_builder_input": replay_builder_input}


def _why_loaded_context_changed(continuity_mode: str, round_number: int) -> str:
    if continuity_mode == "control_current_replay":
        return (
            "Initial round seeded from the frozen control replay path."
            if round_number == 1
            else "Control round refreshed the current requirement draft and prior auditor output."
        )
    if continuity_mode == "v1_compiled_shared_state":
        return (
            "Initial V1 round projected the compiled shared state into role-specific loaded context."
            if round_number == 1
            else "V1 round refreshed the role-specific compiled shared-state projections from updated authoritative state."
        )
    return (
        "Initial V0 round prepended the bounded replay block built from the locked source history."
        if round_number == 1
        else "V0 round refreshed the bounded replay block from updated authoritative source history."
    )


def _role_view(
    *,
    role: str,
    round_number: int,
    loaded_context: str | None,
    prompt_tokens: int | None,
    continuity_mode: str,
    role_focus: str | None = None,
) -> dict[str, Any]:
    source_refs = [{"source_input_id": f"task_brief_r{round_number}", "relationship": "included_task"}]
    source_refs.append(
        {"source_input_id": f"current_requirement_r{round_number}", "relationship": "included_requirement"}
    )
    if role == "auditor":
        source_refs.append(
            {"source_input_id": f"architect_output_r{round_number}", "relationship": "included_architect_output"}
        )
    payload = {
        "role": role,
        "provider_request_token_count": prompt_tokens,
        "derived_from": {
            "source_input_refs": source_refs,
            "mode_artifact_refs": (
                [{"artifact_id": f"v0_replay_r{round_number}", "relationship": "included_replay_block"}]
                if continuity_mode == "v0_log_derived_replay"
                else [{"artifact_id": f"v1_state_r{round_number}", "relationship": "compiled_from_shared_state"}]
                if continuity_mode == "v1_compiled_shared_state"
                else []
            ),
        },
    }
    if role_focus is not None:
        return {**payload, "role_focus": role_focus}
    return {**payload, "loaded_context": str(loaded_context or "")}


def _prepare_round_context(
    *,
    config: dict[str, Any],
    scenario_input: dict[str, Any],
    continuity_mode: str,
    round_number: int,
    task: str,
    current_requirement: str,
    prior_auditor_output: str,
    latest_trace: dict[str, Any] | None,
    prior_v1_state_payload: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, Any], str, list[dict[str, str]], dict[str, str]]:
    source_inputs = _base_source_inputs(
        round_number=round_number,
        scenario_input=scenario_input,
        task=task,
        current_requirement=current_requirement,
        prior_auditor_output=prior_auditor_output,
    )
    continuity_context_by_role = {"architect": "", "auditor": ""}
    role_focus_by_role: dict[str, str] = {}
    continuity_context, mode_artifacts = _continuity_context_bundle(
        continuity_mode=continuity_mode,
        scenario_input=scenario_input,
        current_requirement=current_requirement,
        prior_auditor_output=prior_auditor_output,
        latest_trace=latest_trace,
        round_number=round_number,
        config_path=Path(str(config["config_path"])),
    )
    if continuity_mode == "v0_log_derived_replay":
        continuity_context_by_role = {"architect": continuity_context, "auditor": continuity_context}
    if continuity_mode == "v1_compiled_shared_state":
        shared_state_snapshot, role_views = build_v1_pre_round_state(
            source_inputs=source_inputs,
            current_requirement=current_requirement,
            round_number=round_number,
            prior_state_payload=prior_v1_state_payload,
            latest_trace=latest_trace,
            v1_state_contract_path=Path(str(config["v1_state_contract_path"])),
            architect_focus=V1_ARCHITECT_FOCUS,
            auditor_focus=V1_AUDITOR_FOCUS,
        )
        mode_artifacts = {"shared_state_snapshot": shared_state_snapshot}
        continuity_context_by_role = {
            "architect": str(role_views["architect"]["loaded_context"]),
            "auditor": str(role_views["auditor"]["loaded_context"]),
        }
        role_focus_by_role = {
            "architect": V1_ARCHITECT_FOCUS,
            "auditor": V1_AUDITOR_FOCUS,
        }
    architect_user = architect_user_content(
        task=task,
        current_requirement=current_requirement,
        prior_auditor_output=prior_auditor_output,
        continuity_context=continuity_context_by_role["architect"],
    )
    architect_rules = _prompt_hardening_rules(config, role="architect", round_number=round_number)
    architect_messages = [
        build_architect_messages(
            task=task,
            current_requirement=current_requirement,
            prior_auditor_output=prior_auditor_output,
            extra_rules=architect_rules,
        )[0],
        {"role": "user", "content": architect_user},
    ]
    return source_inputs, continuity_context_by_role, mode_artifacts, architect_user, architect_messages, role_focus_by_role


async def _execute_round_turn(
    *,
    config: dict[str, Any],
    pair: Any,
    task: str,
    auditor_continuity_context: str,
    architect_messages: list[dict[str, str]],
    round_number: int,
    source_inputs: list[dict[str, Any]],
    role_timeout_sec: int,
) -> tuple[str, list[dict[str, Any]], int, int | None, str, int, int | None, list[dict[str, str]]]:
    architect_raw, _architect_response_raw, architect_latency_ms, architect_prompt_tokens = await _call_role(
        model=str(pair.architect_model),
        provider_name=str(pair.architect_provider),
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
    auditor_user = auditor_user_content(
        task=task,
        architect_output=architect_raw,
        continuity_context=auditor_continuity_context,
    )
    auditor_rules = _prompt_hardening_rules(config, role="auditor", round_number=round_number)
    auditor_messages = [
        build_auditor_messages(task=task, architect_output=architect_raw, extra_rules=auditor_rules)[0],
        {"role": "user", "content": auditor_user},
    ]
    auditor_raw, _auditor_response_raw, auditor_latency_ms, auditor_prompt_tokens = await _call_role(
        model=str(pair.auditor_model),
        provider_name=str(pair.auditor_provider),
        messages=auditor_messages,
        timeout_sec=role_timeout_sec,
    )
    return (
        architect_raw,
        source_inputs,
        architect_latency_ms,
        architect_prompt_tokens,
        auditor_raw,
        auditor_latency_ms,
        auditor_prompt_tokens,
        auditor_messages,
    )


async def run_live_scenario_mode(
    *,
    config: dict[str, Any],
    pair: Any,
    scenario_input: dict[str, Any],
    continuity_mode: str,
    locked_budget: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    role_timeout_sec = int(config.get("role_timeout_sec") or 120)
    task = _scenario_brief(scenario_input)
    current_requirement = str(scenario_input.get("R0") or "")
    prior_auditor_output = ""
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
            role_focus_by_role,
        ) = _prepare_round_context(
            config=config,
            scenario_input=scenario_input,
            continuity_mode=continuity_mode,
            round_number=round_number,
            task=task,
            current_requirement=current_requirement,
            prior_auditor_output=prior_auditor_output,
            latest_trace=latest_trace,
            prior_v1_state_payload=prior_v1_state_payload,
        )
        (
            architect_raw,
            source_inputs,
            architect_latency_ms,
            architect_prompt_tokens,
            auditor_raw,
            auditor_latency_ms,
            auditor_prompt_tokens,
            auditor_messages,
        ) = await _execute_round_turn(
            config=config,
            pair=pair,
            task=task,
            auditor_continuity_context=continuity_context_by_role["auditor"],
            architect_messages=architect_messages,
            round_number=round_number,
            source_inputs=source_inputs,
            role_timeout_sec=role_timeout_sec,
        )
        auditor_user = auditor_messages[1]["content"]

        state = run_round(state, architect_raw, auditor_raw, cfg)
        latest_trace = state.history_rounds[-1] if state.history_rounds else None
        round_rows.append(
            {
                "trace": latest_trace,
                "round_latency_ms": architect_latency_ms + auditor_latency_ms,
                "round_active_context_size_bytes": max(_prompt_bytes(architect_messages), _prompt_bytes(auditor_messages)),
                "round_active_context_size_tokens": _max_optional(architect_prompt_tokens, auditor_prompt_tokens),
            }
        )
        inspect_rounds.append(
            {
                "round_index": round_number - 1,
                "why_loaded_context_changed": _why_loaded_context_changed(continuity_mode, round_number),
                "source_inputs": source_inputs,
                "mode_artifacts": mode_artifacts,
                "role_views": [
                    _role_view(
                        role="architect",
                        round_number=round_number,
                        loaded_context=architect_user if continuity_mode != "v1_compiled_shared_state" else None,
                        prompt_tokens=architect_prompt_tokens,
                        continuity_mode=continuity_mode,
                        role_focus=role_focus_by_role.get("architect") if continuity_mode == "v1_compiled_shared_state" else None,
                    ),
                    _role_view(
                        role="auditor",
                        round_number=round_number,
                        loaded_context=auditor_user if continuity_mode != "v1_compiled_shared_state" else None,
                        prompt_tokens=auditor_prompt_tokens,
                        continuity_mode=continuity_mode,
                        role_focus=role_focus_by_role.get("auditor") if continuity_mode == "v1_compiled_shared_state" else None,
                    ),
                ],
            }
        )
        if isinstance(latest_trace, dict) and str(latest_trace.get("validity_verdict") or "") == "valid":
            next_requirement = str((latest_trace.get("architect_parsed") or {}).get("requirement") or "").strip()
            if next_requirement:
                current_requirement = next_requirement
        prior_auditor_output = auditor_raw
        if continuity_mode == "v1_compiled_shared_state":
            post_round_source_inputs = _base_source_inputs(
                round_number=round_number,
                scenario_input=scenario_input,
                task=task,
                current_requirement=current_requirement,
                prior_auditor_output=prior_auditor_output,
            )
            post_round_state = build_v1_post_round_state(
                source_inputs=post_round_source_inputs,
                current_requirement=current_requirement,
                round_number=round_number,
                prior_state_payload=prior_v1_state_payload,
                latest_trace=latest_trace,
                v1_state_contract_path=Path(str(config["v1_state_contract_path"])),
            )
            prior_v1_state_payload = dict(post_round_state["payload"])
            v1_state_history.append({"artifact_body": dict(post_round_state["payload"])})
        if state.stop_reason is not None:
            break

    final_requirement = current_requirement
    if isinstance(latest_trace, dict):
        final_requirement = str((latest_trace.get("architect_parsed") or {}).get("requirement") or final_requirement).strip()
    metrics = (
        compute_v1_continuity_run_metrics(v1_state_history)
        if continuity_mode == "v1_compiled_shared_state"
        else compute_continuity_run_metrics(round_rows, final_requirement)
    )
    compare_row = {
        "pair_id": str(pair.pair_id),
        "scenario_id": str(scenario_input["id"]),
        "continuity_mode": continuity_mode,
        "locked_budget": int(locked_budget),
        "converged": str(state.stop_reason or "") in CONVERGED_STOP_REASONS,
        "stop_reason": str(state.stop_reason or "NONE"),
        "rounds_consumed": len(round_rows),
        **metrics,
        "round_latency_ms": [row["round_latency_ms"] for row in round_rows],
        "round_active_context_size_bytes": [row["round_active_context_size_bytes"] for row in round_rows],
        "round_active_context_size_tokens": [
            row["round_active_context_size_tokens"] for row in round_rows if row["round_active_context_size_tokens"] is not None
        ],
    }
    inspect_row = {
        "pair_id": str(pair.pair_id),
        "scenario_id": str(scenario_input["id"]),
        "continuity_mode": continuity_mode,
        "locked_budget": int(locked_budget),
        "rounds": inspect_rounds,
    }
    return inspect_row, compare_row


async def run_context_continuity_live_proof(*, config_path: Path | None = None) -> dict[str, Any]:
    config = load_lane_config(config_path)
    pair = config["selected_primary_pairs"][0]
    scenario_index = {str(row["id"]): row for row in _load_scenarios()}
    scenario_inputs = [_load_scenario_inputs(scenario_index[scenario_id]) for scenario_id in config["scenario_set"]["scenario_ids"]]
    inspect_runs: list[dict[str, Any]] = []
    compare_rows: list[dict[str, Any]] = []
    for locked_budget in config["locked_budgets"]:
        for continuity_mode in ("control_current_replay", "v0_log_derived_replay", "v1_compiled_shared_state"):
            for scenario_input in scenario_inputs:
                inspect_row, compare_row = await run_live_scenario_mode(
                    config=config,
                    pair=pair,
                    scenario_input=scenario_input,
                    continuity_mode=continuity_mode,
                    locked_budget=int(locked_budget),
                )
                inspect_runs.append(inspect_row)
                compare_rows.append(compare_row)

    inspectability_input = {"schema_version": "odr.context_continuity.inspectability_input.v1", "scenario_runs": inspect_runs}
    inspectability_out = resolve_lane_artifact_path(config, "inspectability_output")
    inspectability_payload = build_inspectability_payload(config, inspectability_input)
    inspectability_payload["artifact_locations"]["inspectability_output"] = str(inspectability_out)
    inspectability_persisted = write_payload_with_diff_ledger(inspectability_out, inspectability_payload)

    compare_out = resolve_default_compare_output_path(Path(str(config["config_path"])))
    compare_payload = build_context_continuity_compare_payload_from_rows(compare_rows, config_path=Path(str(config["config_path"])))
    compare_persisted = write_payload_with_diff_ledger(compare_out, compare_payload)

    verdict_out = resolve_default_verdict_output_path(Path(str(config["config_path"])))
    verdict_payload = build_context_continuity_verdict_payload_from_payload(
        {**compare_payload, "compare_payload_path": str(compare_out)},
        config_path=Path(str(config["config_path"])),
    )
    verdict_persisted = write_payload_with_diff_ledger(verdict_out, verdict_payload)
    return {
        "inspectability_output": str(inspectability_out),
        "compare_output": str(compare_out),
        "verdict_output": str(verdict_out),
        "inspectability_payload": inspectability_persisted,
        "compare_payload": compare_persisted,
        "verdict_payload": verdict_persisted,
    }
