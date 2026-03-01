from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from random import Random
from statistics import median
from typing import Any

from .canonical import canonical_json, hash_state
from .contracts import RuleSystem, Strategy, TerminalResult
from .detectors import cycle_anomaly, deadlock_anomaly, illegal_action_anomaly
from .types import RunConfig


def _derive_int(*parts: Any) -> int:
    material = "|".join(str(part) for part in parts).encode("utf-8")
    digest = hashlib.sha256(material).hexdigest()
    return int(digest[:16], 16)


@dataclass
class EpisodeResult:
    episode_id: str
    terminal_result: TerminalResult
    step_index: int
    action_counts: dict[str, dict[str, int]] = field(default_factory=dict)
    anomalies: list[dict[str, Any]] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)
    illegal_action_count: int = 0


@dataclass
class BatchResult:
    episodes: list[EpisodeResult]
    summary: dict[str, Any]
    probes: dict[str, dict[str, Any]]
    interrupted: bool = False


def _terminal(reason: str, winners: list[str] | None = None) -> TerminalResult:
    return TerminalResult(reason=reason, winners=list(winners or []), scores=None)


class RuleSystemContractError(RuntimeError):
    pass


def _state_canonical(rulesystem: RuleSystem, state: Any) -> tuple[str, str]:
    first = rulesystem.serialize_state(state)
    first_cjson = canonical_json(first, root_path="state")
    second = rulesystem.serialize_state(state)
    second_cjson = canonical_json(second, root_path="state")
    if first_cjson != second_cjson:
        raise RuleSystemContractError("RuleSystem.serialize_state is non-deterministic for the same state snapshot")
    return first_cjson, hash_state(first)


def _state_digest(rulesystem: RuleSystem, state: Any) -> str:
    _, digest = _state_canonical(rulesystem, state)
    return digest


def _canonical_legal_actions(rulesystem: RuleSystem, legal_actions: list[Any]) -> list[str]:
    return [canonical_json(rulesystem.serialize_action(action), root_path="action") for action in legal_actions]


def run_episode(
    *,
    rulesystem: RuleSystem,
    run_config: RunConfig,
    episode_index: int,
    strategy_map: dict[str, Strategy],
) -> EpisodeResult:
    episode_id = f"episode_{episode_index:05d}"
    agents = [agent.id for agent in run_config.agents]
    turn_order = [str(item) for item in run_config.scenario.get("turn_order", [])]
    if not turn_order:
        raise ValueError("scenario.turn_order must be non-empty")
    state = rulesystem.initial_state(
        run_config.run_seed + episode_index,
        run_config.scenario,
        run_config.ruleset,
        agents,
    )
    digest0 = _state_digest(rulesystem, state)
    seen_digests: dict[str, int] = {digest0: 0}
    pending_skips: set[str] = set()
    step_index = 0
    anomalies: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []
    action_counts: dict[str, dict[str, int]] = {agent_id: {} for agent_id in agents}
    terminal_result: TerminalResult | None = None
    illegal_action_count = 0

    while step_index < run_config.max_steps and terminal_result is None:
        for agent_id in turn_order:
            terminal_now = rulesystem.is_terminal(state)
            if terminal_now is not None:
                terminal_result = terminal_now
                break
            if agent_id in pending_skips:
                pending_skips.remove(agent_id)
                step_index += 1
                if step_index >= run_config.max_steps:
                    break
                continue

            state_before_turn, _ = _state_canonical(rulesystem, state)
            legal_actions = rulesystem.legal_actions(state, agent_id)
            if run_config.enforce_contract_checks:
                state_after_legal_1, _ = _state_canonical(rulesystem, state)
                if state_before_turn != state_after_legal_1:
                    raise RuleSystemContractError("RuleSystem.legal_actions mutated input state")
                legal_actions_second = rulesystem.legal_actions(state, agent_id)
                if _canonical_legal_actions(rulesystem, legal_actions) != _canonical_legal_actions(
                    rulesystem, legal_actions_second
                ):
                    raise RuleSystemContractError("RuleSystem.legal_actions is non-deterministic for same state snapshot")
                state_after_legal_2, _ = _state_canonical(rulesystem, state)
                if state_before_turn != state_after_legal_2:
                    raise RuleSystemContractError("RuleSystem.legal_actions mutated input state")
            if not legal_actions:
                state_digest = _state_digest(rulesystem, state)
                anomalies.append(deadlock_anomaly(agent_id=agent_id, step_index=step_index, state_digest=state_digest))
                terminal_result = _terminal("deadlock")
                break

            observation = rulesystem.observe(state, agent_id)
            if run_config.enforce_contract_checks:
                state_after_observe_1, _ = _state_canonical(rulesystem, state)
                if state_before_turn != state_after_observe_1:
                    raise RuleSystemContractError("RuleSystem.observe mutated input state")
                observation_second = rulesystem.observe(state, agent_id)
                obs_first = canonical_json(observation, root_path="observation")
                obs_second = canonical_json(observation_second, root_path="observation")
                if obs_first != obs_second:
                    raise RuleSystemContractError("RuleSystem.observe is non-deterministic for same state snapshot")
                state_after_observe_2, _ = _state_canonical(rulesystem, state)
                if state_before_turn != state_after_observe_2:
                    raise RuleSystemContractError("RuleSystem.observe mutated input state")
            strategy = strategy_map.get(agent_id)
            if strategy is None:
                raise ValueError(f"missing strategy for agent {agent_id}")
            agent_step_seed = _derive_int(run_config.run_seed, episode_index, agent_id, step_index)
            rng = Random(agent_step_seed)
            action = strategy.select_action(
                observation,
                legal_actions,
                rng,
                {"agent_id": agent_id, "step_index": step_index, "rulesystem": rulesystem},
            )
            legal_cjson = {canonical_json(rulesystem.serialize_action(a)): a for a in legal_actions}
            attempted_cjson = canonical_json(rulesystem.serialize_action(action))
            if attempted_cjson not in legal_cjson:
                illegal_action_count += 1
                anomalies.append(
                    illegal_action_anomaly(
                        agent_id=agent_id,
                        step_index=step_index,
                        action_key=rulesystem.action_key(action),
                        attempted_action_cjson=attempted_cjson,
                        legal_action_keys=[rulesystem.action_key(item) for item in legal_actions],
                    )
                )
                if run_config.illegal_action_policy == "terminal_invalid_action":
                    terminal_result = _terminal("invalid_action")
                    break
                action = legal_actions[0]

            digest_before = _state_digest(rulesystem, state)
            state_input = state
            state_snapshot_before_apply, _ = _state_canonical(rulesystem, state_input)
            transition = rulesystem.apply_action(state_input, agent_id, action)
            if run_config.enforce_contract_checks:
                state_after_apply_input, _ = _state_canonical(rulesystem, state_input)
                if state_snapshot_before_apply != state_after_apply_input:
                    raise RuleSystemContractError("RuleSystem.apply_action mutated input state in place")
                if transition.next_state is state_input:
                    raise RuleSystemContractError("RuleSystem.apply_action returned the input state object (in-place update)")
            state = transition.next_state
            if transition.skip_agent:
                pending_skips.add(str(transition.skip_agent))
            digest_after = _state_digest(rulesystem, state)
            action_key = rulesystem.action_key(action)
            action_counts.setdefault(agent_id, {})
            action_counts[agent_id][action_key] = action_counts[agent_id].get(action_key, 0) + 1
            trace.append(
                {
                    "step_index": step_index,
                    "agent_id": agent_id,
                    "action_key": action_key,
                    "state_digest_before": digest_before,
                    "state_digest_after": digest_after,
                    "terminal": None,
                }
            )
            if digest_after in seen_digests:
                entry_step = seen_digests[digest_after]
                anomalies.append(
                    cycle_anomaly(
                        cycle_entry_step=entry_step,
                        cycle_length=(step_index + 1) - entry_step,
                        step_index=step_index,
                        state_digest=digest_after,
                    )
                )
                terminal_result = _terminal("cycle_detected")
                break
            seen_digests[digest_after] = step_index + 1
            step_index += 1
            if step_index >= run_config.max_steps:
                break

    if terminal_result is None:
        terminal_result = _terminal("timeout")
    return EpisodeResult(
        episode_id=episode_id,
        terminal_result=terminal_result,
        step_index=step_index,
        action_counts=action_counts,
        anomalies=anomalies,
        trace=trace,
        illegal_action_count=illegal_action_count,
    )


def aggregate_summary(
    *,
    run_config: RunConfig,
    episodes: list[EpisodeResult],
    extra_anomalies: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    total = len(episodes)
    terminal_reason_distribution: dict[str, int] = {}
    wins: dict[str, int] = {agent.id: 0 for agent in run_config.agents}
    action_histogram: dict[str, int] = {}
    action_with_alternatives: dict[str, int] = {}
    steps: list[int] = []
    anomaly_counts = {"cycle_detected": 0, "deadlock": 0, "illegal_action_attempt": 0}
    illegal_action_episodes = 0
    suspicious: list[dict[str, Any]] = []
    for episode in episodes:
        reason = episode.terminal_result.reason
        terminal_reason_distribution[reason] = terminal_reason_distribution.get(reason, 0) + 1
        steps.append(episode.step_index)
        for winner in episode.terminal_result.winners:
            wins[winner] = wins.get(winner, 0) + 1
        episode_has_illegal = False
        for agent_counts in episode.action_counts.values():
            for action_key, count in agent_counts.items():
                action_histogram[action_key] = action_histogram.get(action_key, 0) + count
        for event in episode.trace:
            action_key = str(event.get("action_key") or "")
            if action_key:
                action_with_alternatives[action_key] = action_with_alternatives.get(action_key, 0) + 1
        for anomaly in episode.anomalies:
            anomaly_type = str(anomaly.get("type") or "")
            if anomaly_type in anomaly_counts:
                anomaly_counts[anomaly_type] += 1
            if anomaly_type == "illegal_action_attempt":
                episode_has_illegal = True
            suspicious.append(
                {
                    "episode_id": episode.episode_id,
                    "type": anomaly_type,
                    "severity": int(anomaly.get("severity", 0)),
                    "step_index": int(anomaly.get("step_index", episode.step_index)),
                }
            )
        if episode_has_illegal:
            illegal_action_episodes += 1
    top_findings = sorted(
        suspicious,
        key=lambda row: (-int(row["severity"]), int(row["step_index"]), str(row["episode_id"])),
    )[:20]
    avg_steps = (sum(steps) / total) if total > 0 else 0.0
    med_steps = median(steps) if steps else 0
    win_rate = {agent_id: (count / total if total > 0 else 0.0) for agent_id, count in wins.items()}
    payload = {
        "episodes": total,
        "win_rate": win_rate,
        "terminal_reason_distribution": terminal_reason_distribution,
        "avg_steps": round(avg_steps, 6),
        "median_steps": med_steps,
        "action_key_histogram": action_histogram,
        "anomaly_incidence": {
            "cycle_detected": anomaly_counts["cycle_detected"] / total if total else 0.0,
            "deadlock": anomaly_counts["deadlock"] / total if total else 0.0,
            "illegal_action_attempt": anomaly_counts["illegal_action_attempt"] / total if total else 0.0,
        },
        "illegal_action_rate": illegal_action_episodes / total if total else 0.0,
        "top_findings": top_findings,
    }
    if extra_anomalies:
        payload["run_hints"] = list(extra_anomalies)
    return payload
