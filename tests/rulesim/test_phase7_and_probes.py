from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from orket.rulesim.canonical import StateSerializationError, hash_state
from orket.rulesim.contracts import TerminalResult, TransitionResult
from orket.rulesim.runner import run_episode
from orket.rulesim.strategies.random_uniform import RandomUniformStrategy
from orket.rulesim.types import parse_run_config
from orket.rulesim.workload import run_rulesim_v0_sync


class _TimeoutRuleSystem:
    def initial_state(self, seed: int, scenario: dict[str, Any], ruleset: dict[str, Any], agents: list[str]) -> dict[str, Any]:
        return {"tick": 0}

    def legal_actions(self, state: dict[str, Any], agent_id: str) -> list[dict[str, Any]]:
        return [{"kind": "advance"}]

    def apply_action(self, state: dict[str, Any], agent_id: str, action: dict[str, Any]) -> TransitionResult:
        return TransitionResult(next_state={"tick": int(state["tick"]) + 1})

    def is_terminal(self, state: dict[str, Any]) -> TerminalResult | None:
        return None

    def observe(self, state: dict[str, Any], agent_id: str) -> dict[str, Any]:
        return dict(state)

    def hash_state(self, state: dict[str, Any]) -> str:
        return hash_state(self.serialize_state(state))

    def serialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return dict(state)

    def serialize_action(self, action: dict[str, Any]) -> dict[str, Any]:
        return dict(action)

    def action_key(self, action: dict[str, Any]) -> str:
        return str(action.get("kind") or "")


class _SkipOtherRuleSystem(_TimeoutRuleSystem):
    def initial_state(self, seed: int, scenario: dict[str, Any], ruleset: dict[str, Any], agents: list[str]) -> dict[str, Any]:
        return {"turns": 0, "log": []}

    def apply_action(self, state: dict[str, Any], agent_id: str, action: dict[str, Any]) -> TransitionResult:
        turns = int(state["turns"]) + 1
        log = list(state["log"])
        log.append(agent_id)
        skip_agent = "agent_1" if turns == 1 else None
        return TransitionResult(next_state={"turns": turns, "log": log}, skip_agent=skip_agent)

    def is_terminal(self, state: dict[str, Any]) -> TerminalResult | None:
        if state["log"] == ["agent_0", "agent_0", "agent_1"]:
            return TerminalResult(reason="win", winners=["agent_0"])
        return None


class _SkipSelfRuleSystem(_TimeoutRuleSystem):
    def initial_state(self, seed: int, scenario: dict[str, Any], ruleset: dict[str, Any], agents: list[str]) -> dict[str, Any]:
        return {"actions": 0}

    def apply_action(self, state: dict[str, Any], agent_id: str, action: dict[str, Any]) -> TransitionResult:
        actions = int(state["actions"]) + 1
        skip_agent = "agent_0" if actions == 1 else None
        return TransitionResult(next_state={"actions": actions}, skip_agent=skip_agent)

    def is_terminal(self, state: dict[str, Any]) -> TerminalResult | None:
        if int(state["actions"]) >= 2:
            return TerminalResult(reason="draw", winners=[])
        return None


class _BadStateRuleSystem(_TimeoutRuleSystem):
    def serialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {"bad": object()}


class _AlwaysFirstStrategy:
    def select_action(self, observation: Any, legal_actions: list[Any], rng: Random, context: dict[str, Any]) -> Any:
        return legal_actions[0]


def test_timeout_reason_fires_at_max_steps() -> None:
    config = parse_run_config(
        {
            "rulesystem_id": "x",
            "run_seed": 1,
            "episodes": 1,
            "max_steps": 3,
            "agents": [{"id": "agent_0", "strategy": "random_uniform", "params": {}}],
            "scenario": {"turn_order": ["agent_0"]},
        }
    )
    episode = run_episode(
        rulesystem=_TimeoutRuleSystem(),
        run_config=config,
        episode_index=0,
        strategy_map={"agent_0": RandomUniformStrategy()},
    )
    assert episode.terminal_result.reason == "timeout"
    assert episode.step_index == 3


def test_skip_agent_single_occurrence_semantics() -> None:
    config = parse_run_config(
        {
            "rulesystem_id": "x",
            "run_seed": 1,
            "episodes": 1,
            "max_steps": 8,
            "agents": [
                {"id": "agent_0", "strategy": "random_uniform", "params": {}},
                {"id": "agent_1", "strategy": "random_uniform", "params": {}},
            ],
            "scenario": {"turn_order": ["agent_0", "agent_1"]},
        }
    )
    episode = run_episode(
        rulesystem=_SkipOtherRuleSystem(),
        run_config=config,
        episode_index=0,
        strategy_map={"agent_0": _AlwaysFirstStrategy(), "agent_1": _AlwaysFirstStrategy()},
    )
    assert episode.terminal_result.reason == "win"
    assert [row["agent_id"] for row in episode.trace] == ["agent_0", "agent_0", "agent_1"]
    assert [row["step_index"] for row in episode.trace] == [0, 2, 3]


def test_skip_self_applies_to_next_turn_only() -> None:
    config = parse_run_config(
        {
            "rulesystem_id": "x",
            "run_seed": 1,
            "episodes": 1,
            "max_steps": 5,
            "agents": [{"id": "agent_0", "strategy": "random_uniform", "params": {}}],
            "scenario": {"turn_order": ["agent_0"]},
        }
    )
    episode = run_episode(
        rulesystem=_SkipSelfRuleSystem(),
        run_config=config,
        episode_index=0,
        strategy_map={"agent_0": _AlwaysFirstStrategy()},
    )
    assert episode.terminal_result.reason == "draw"
    assert [row["step_index"] for row in episode.trace] == [0, 2]


def test_non_serializable_state_raises_configuration_error_with_path() -> None:
    config = parse_run_config(
        {
            "rulesystem_id": "x",
            "run_seed": 1,
            "episodes": 1,
            "max_steps": 2,
            "agents": [{"id": "agent_0", "strategy": "random_uniform", "params": {}}],
            "scenario": {"turn_order": ["agent_0"]},
        }
    )
    with pytest.raises(StateSerializationError) as exc:
        run_episode(
            rulesystem=_BadStateRuleSystem(),
            run_config=config,
            episode_index=0,
            strategy_map={"agent_0": _AlwaysFirstStrategy()},
        )
    assert 'state["bad"]' in str(exc.value)


def test_probe_variant_override_merges_and_writes_probe_artifacts(tmp_path: Path) -> None:
    result = run_rulesim_v0_sync(
        input_config={
            "schema_version": "rulesim_v0",
            "rulesystem_id": "loop",
            "run_seed": 11,
            "episodes": 3,
            "max_steps": 6,
            "agents": [{"id": "agent_0", "strategy": "random_uniform", "params": {}}],
            "scenario": {"turn_order": ["agent_0"]},
            "artifact_policy": "none",
            "probes": [
                {"probe_id": "p_timeout", "episode_count": 2, "variant_overrides": {"max_steps": 1}},
            ],
        },
        workspace_path=tmp_path,
    )
    root = Path(result["artifact_root"])
    probe_summary = json.loads((root / "probes" / "p_timeout" / "summary.json").read_text(encoding="utf-8"))
    assert probe_summary["terminal_reason_distribution"]["timeout"] == 2
    assert (root / "probes" / "p_timeout" / "episodes.csv").exists()
    assert (root / "result.json").exists()
