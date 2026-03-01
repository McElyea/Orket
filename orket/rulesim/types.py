from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

AgentId = str
State = Any
Action = Any
Observation = Any


@dataclass(frozen=True)
class AgentConfig:
    id: str
    strategy: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProbeConfig:
    probe_id: str
    variant_overrides: dict[str, Any] = field(default_factory=dict)
    episode_count: int = 0
    selection_policy: str | None = None


@dataclass(frozen=True)
class RunConfig:
    rulesystem_id: str
    run_seed: int
    episodes: int
    max_steps: int
    agents: tuple[AgentConfig, ...]
    scenario: dict[str, Any]
    ruleset: dict[str, Any] = field(default_factory=dict)
    illegal_action_policy: str = "substitute_first"
    probes: tuple[ProbeConfig, ...] = field(default_factory=tuple)
    artifact_policy: str = "suspicious_only"
    detector_thresholds: dict[str, float] = field(default_factory=dict)
    schema_version: str = "rulesim_v0"
    enforce_contract_checks: bool = True
    episode_delay_ms: int = 0
    graceful_cancel_file: str | None = None
    checkpoint_dir: str | None = None


def parse_run_config(input_config: dict[str, Any]) -> RunConfig:
    rulesystem_id = str(input_config.get("rulesystem_id") or "").strip()
    if not rulesystem_id:
        raise ValueError("rulesystem_id is required")
    episodes = int(input_config.get("episodes", 0))
    max_steps = int(input_config.get("max_steps", 0))
    run_seed = int(input_config.get("run_seed", 0))
    if episodes <= 0:
        raise ValueError("episodes must be > 0")
    if max_steps <= 0:
        raise ValueError("max_steps must be > 0")
    raw_agents = input_config.get("agents")
    if not isinstance(raw_agents, list) or not raw_agents:
        raise ValueError("agents must be a non-empty list")
    agents: list[AgentConfig] = []
    for row in raw_agents:
        if not isinstance(row, dict):
            raise ValueError("agent entry must be an object")
        agent_id = str(row.get("id") or "").strip()
        strategy = str(row.get("strategy") or "").strip()
        if not agent_id or not strategy:
            raise ValueError("agent.id and agent.strategy are required")
        params = row.get("params")
        agents.append(AgentConfig(id=agent_id, strategy=strategy, params=dict(params or {})))
    scenario = input_config.get("scenario")
    if not isinstance(scenario, dict):
        raise ValueError("scenario must be an object")
    turn_order = scenario.get("turn_order")
    if not isinstance(turn_order, list) or not turn_order:
        raise ValueError("scenario.turn_order must be a non-empty list")
    ruleset = input_config.get("ruleset")
    probes: list[ProbeConfig] = []
    for row in input_config.get("probes") or []:
        if not isinstance(row, dict):
            raise ValueError("probe entry must be an object")
        probe_id = str(row.get("probe_id") or "").strip()
        if not probe_id:
            raise ValueError("probe_id is required")
        overrides = dict(row.get("variant_overrides") or {})
        episode_count = int(row.get("episode_count", 0))
        probes.append(
            ProbeConfig(
                probe_id=probe_id,
                variant_overrides=overrides,
                episode_count=episode_count,
                selection_policy=str(row.get("selection_policy") or "").strip() or None,
            )
        )
    illegal_action_policy = str(input_config.get("illegal_action_policy") or "substitute_first").strip()
    if illegal_action_policy not in {"substitute_first", "terminal_invalid_action"}:
        raise ValueError("illegal_action_policy must be substitute_first or terminal_invalid_action")
    artifact_policy = str(input_config.get("artifact_policy") or "suspicious_only").strip()
    if artifact_policy not in {"none", "suspicious_only", "all"}:
        raise ValueError("artifact_policy must be none, suspicious_only, or all")
    episode_delay_ms = int(input_config.get("episode_delay_ms", 0))
    if episode_delay_ms < 0:
        raise ValueError("episode_delay_ms must be >= 0")
    enforce_contract_checks = bool(input_config.get("enforce_contract_checks", True))
    graceful_cancel_file_raw = str(input_config.get("graceful_cancel_file") or "").strip()
    checkpoint_dir_raw = str(input_config.get("checkpoint_dir") or "").strip()
    return RunConfig(
        rulesystem_id=rulesystem_id,
        run_seed=run_seed,
        episodes=episodes,
        max_steps=max_steps,
        agents=tuple(agents),
        scenario=dict(scenario),
        ruleset=dict(ruleset or {}),
        illegal_action_policy=illegal_action_policy,
        probes=tuple(probes),
        artifact_policy=artifact_policy,
        detector_thresholds=dict(input_config.get("detector_thresholds") or {}),
        schema_version=str(input_config.get("schema_version") or "rulesim_v0").strip() or "rulesim_v0",
        enforce_contract_checks=enforce_contract_checks,
        episode_delay_ms=episode_delay_ms,
        graceful_cancel_file=graceful_cancel_file_raw or None,
        checkpoint_dir=checkpoint_dir_raw or None,
    )
