from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

from orket.streaming.contracts import CommitIntent, StreamEventType
from orket.streaming.manager import InteractionContext

from .artifacts import write_artifact_bundle, write_checkpoint_episode
from .canonical import canonical_json
from .metrics import compute_run_hints
from .runner import BatchResult, RuleSystemContractError, aggregate_summary, run_episode
from .strategies import GreedyHeuristicStrategy, MixedStrategy, RandomUniformStrategy, ScriptedStrategy
from .toys import build_toy_rulesystem
from .types import AgentConfig, RunConfig, parse_run_config


def _merge_dict(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge_dict(dict(out[key]), value)
        else:
            out[key] = value
    return out


def _strategy_for_agent(agent: AgentConfig, run_config: RunConfig):
    normalized = str(agent.strategy).strip().lower()
    if normalized == "random_uniform":
        return RandomUniformStrategy()
    if normalized == "greedy_heuristic":
        score_map = agent.params.get("score_map") if isinstance(agent.params, dict) else None
        return GreedyHeuristicStrategy(score_map=dict(score_map or {}))
    if normalized == "scripted":
        sequence = list((agent.params or {}).get("sequence") or [])
        return ScriptedStrategy(sequence=sequence)
    if normalized == "mixed":
        branches = list((agent.params or {}).get("strategies") or [])
        weighted = []
        for branch in branches:
            if not isinstance(branch, dict):
                continue
            weight = float(branch.get("weight", 0.0))
            subtype = AgentConfig(
                id=agent.id,
                strategy=str(branch.get("strategy") or "random_uniform"),
                params=dict(branch.get("params") or {}),
            )
            weighted.append((weight, _strategy_for_agent(subtype, run_config)))
        if weighted:
            return MixedStrategy(weighted)
        return RandomUniformStrategy()
    raise ValueError(f"unknown strategy '{agent.strategy}' for agent '{agent.id}'")


def _run_batch(run_config: RunConfig) -> BatchResult:
    rulesystem = build_toy_rulesystem(run_config.rulesystem_id)
    strategy_map = {agent.id: _strategy_for_agent(agent, run_config) for agent in run_config.agents}
    episodes = []
    interrupted = False
    checkpoint_root = Path(run_config.checkpoint_dir) if run_config.checkpoint_dir else None
    for episode_index in range(run_config.episodes):
        if run_config.graceful_cancel_file and Path(run_config.graceful_cancel_file).exists():
            interrupted = True
            break
        episode = run_episode(
            rulesystem=rulesystem,
            run_config=run_config,
            episode_index=episode_index,
            strategy_map=strategy_map,
        )
        episodes.append(episode)
        if checkpoint_root is not None:
            write_checkpoint_episode(
                checkpoint_root=checkpoint_root,
                episode_payload={
                    "episode_id": episode.episode_id,
                    "terminal_reason": episode.terminal_result.reason,
                    "step_index": episode.step_index,
                    "anomalies": episode.anomalies,
                    "trace": episode.trace,
                },
            )
        if run_config.episode_delay_ms > 0:
            time.sleep(run_config.episode_delay_ms / 1000.0)
    summary = aggregate_summary(run_config=run_config, episodes=episodes)
    run_hints = compute_run_hints(
        action_histogram=dict(summary.get("action_key_histogram") or {}),
        first_agent_id=str(run_config.scenario.get("turn_order")[0]),
        win_rates=dict(summary.get("win_rate") or {}),
        thresholds=run_config.detector_thresholds,
    )
    if run_hints:
        summary["run_hints"] = run_hints

    probe_payloads: dict[str, dict[str, Any]] = {}
    base_payload: dict[str, Any] = {
        "schema_version": run_config.schema_version,
        "rulesystem_id": run_config.rulesystem_id,
        "run_seed": run_config.run_seed,
        "episodes": run_config.episodes,
        "max_steps": run_config.max_steps,
        "agents": [{"id": agent.id, "strategy": agent.strategy, "params": dict(agent.params)} for agent in run_config.agents],
        "scenario": dict(run_config.scenario),
        "ruleset": dict(run_config.ruleset),
        "illegal_action_policy": run_config.illegal_action_policy,
        "artifact_policy": run_config.artifact_policy,
        "detector_thresholds": dict(run_config.detector_thresholds),
    }
    for probe in run_config.probes:
        if probe.episode_count <= 0:
            continue
        probe_input = _merge_dict(base_payload, dict(probe.variant_overrides))
        probe_input["episodes"] = probe.episode_count
        probe_input["probes"] = []
        probe_run = parse_run_config(probe_input)
        probe_episodes = [
            run_episode(
                rulesystem=rulesystem,
                run_config=probe_run,
                episode_index=episode_index,
                strategy_map=strategy_map,
            )
            for episode_index in range(probe.episode_count)
        ]
        probe_summary = aggregate_summary(run_config=probe_run, episodes=probe_episodes)
        probe_payloads[probe.probe_id] = {
            "summary": probe_summary,
            "episodes_csv": [
                {
                    "episode_id": item.episode_id,
                    "terminal_reason": item.terminal_result.reason,
                    "steps": item.step_index,
                    "has_anomaly": bool(item.anomalies),
                }
                for item in probe_episodes
            ],
        }
    if interrupted:
        summary["interrupted"] = True
    return BatchResult(episodes=episodes, summary=summary, probes=probe_payloads, interrupted=interrupted)


def run_rulesim_v0_sync(*, input_config: dict[str, Any], workspace_path: str | Path) -> dict[str, Any]:
    run_config = parse_run_config(input_config)
    try:
        batch = _run_batch(run_config)
    except RuleSystemContractError as exc:
        raise ValueError(f"RuleSystem contract violation: {exc}") from exc
    episode_payloads: list[dict[str, Any]] = []
    suspicious_rows: list[dict[str, Any]] = []
    for episode in batch.episodes:
        episode_payloads.append(
            {
                "episode_id": episode.episode_id,
                "episode": {
                    "episode_id": episode.episode_id,
                    "terminal_result": {
                        "reason": episode.terminal_result.reason,
                        "winners": episode.terminal_result.winners,
                        "scores": episode.terminal_result.scores,
                    },
                    "step_index": episode.step_index,
                    "anomalies": episode.anomalies,
                },
                "trace": episode.trace,
            }
        )
        if episode.anomalies:
            top = sorted(
                episode.anomalies,
                key=lambda row: (-int(row.get("severity", 0)), int(row.get("step_index", episode.step_index))),
            )[0]
            suspicious_rows.append(
                {
                    "episode_id": episode.episode_id,
                    "type": str(top.get("type") or ""),
                    "step_index": int(top.get("step_index", episode.step_index)),
                }
            )
    rank = {"cycle_detected": 5, "deadlock": 4, "illegal_action_attempt": 3, "timeout": 2, "dominance_hint": 1}
    suspicious_rows = sorted(
        suspicious_rows,
        key=lambda row: (-int(rank.get(str(row["type"]), 0)), int(row["step_index"]), str(row["episode_id"])),
    )
    run_payload = {
        "schema_version": run_config.schema_version,
        "rulesystem_id": run_config.rulesystem_id,
        "run_seed": run_config.run_seed,
        "episodes": run_config.episodes,
        "max_steps": run_config.max_steps,
        "agents": [{"id": agent.id, "strategy": agent.strategy, "params": dict(agent.params)} for agent in run_config.agents],
        "scenario": dict(run_config.scenario),
        "ruleset": dict(run_config.ruleset),
        "illegal_action_policy": run_config.illegal_action_policy,
        "artifact_policy": run_config.artifact_policy,
        "enforce_contract_checks": run_config.enforce_contract_checks,
    }
    bundle = write_artifact_bundle(
        workspace=Path(workspace_path),
        run_config_payload=run_payload,
        summary_payload=batch.summary,
        episode_payloads=episode_payloads,
        suspicious_rows=suspicious_rows,
        probe_payloads=batch.probes,
        artifact_policy=run_config.artifact_policy,
    )
    result = {
        "run_id": bundle["run_id"],
        "run_digest": bundle["run_digest"],
        "artifact_root": bundle["artifact_root"],
        "summary_digest": bundle["summary_digest"],
        "top_findings": batch.summary.get("top_findings", []),
        "interrupted": bool(batch.interrupted),
    }
    result_path = Path(bundle["artifact_root"]) / "result.json"
    result_path.write_text(canonical_json(result) + "\n", encoding="utf-8")
    return result


async def run_rulesim_v0(
    *,
    input_config: dict[str, Any],
    turn_params: dict[str, Any],
    interaction_context: InteractionContext,
) -> dict[str, int]:
    workspace_path = str(input_config.get("workspace") or turn_params.get("workspace") or "workspace").strip()
    await interaction_context.emit_event(
        StreamEventType.MODEL_SELECTED,
        {"model_id": "rulesim_v0", "reason": "deterministic_local_workload", "authoritative": False},
    )
    result = run_rulesim_v0_sync(input_config=input_config, workspace_path=workspace_path)
    await interaction_context.emit_event(
        StreamEventType.MODEL_READY,
        {
            "model_id": "rulesim_v0",
            "warm_state": "warm",
            "run_id": result["run_id"],
            "summary_digest": result["summary_digest"],
            "authoritative": False,
        },
    )
    await interaction_context.emit_event(
        StreamEventType.TOKEN_DELTA,
        {
            "delta": hashlib.sha256(canonical_json(result).encode("utf-8")).hexdigest()[:16],
            "index": 0,
            "authoritative": False,
        },
    )
    await interaction_context.request_commit(CommitIntent(type="turn_finalize", ref="rulesim_v0"))
    return {"post_finalize_wait_ms": 0}


def validate_rulesim_v0_start(*, input_config: dict[str, Any], turn_params: dict[str, Any]) -> None:
    parse_run_config(input_config)
