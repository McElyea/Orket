from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any

import pytest

from orket.rulesim.contracts import TerminalResult, TransitionResult
from orket.rulesim.workload import run_rulesim_v0_sync


class _BaseRuleSystem:
    def initial_state(self, seed: int, scenario: dict[str, Any], ruleset: dict[str, Any], agents: list[str]) -> dict[str, Any]:
        return {"tick": 0}

    def legal_actions(self, state: dict[str, Any], agent_id: str) -> list[dict[str, Any]]:
        return [{"kind": "advance"}]

    def apply_action(self, state: dict[str, Any], agent_id: str, action: dict[str, Any]) -> TransitionResult:
        return TransitionResult(next_state={"tick": int(state["tick"]) + 1})

    def is_terminal(self, state: dict[str, Any]) -> TerminalResult | None:
        if int(state["tick"]) >= 1:
            return TerminalResult(reason="draw", winners=[])
        return None

    def observe(self, state: dict[str, Any], agent_id: str) -> dict[str, Any]:
        return {"tick": int(state["tick"])}

    def hash_state(self, state: dict[str, Any]) -> str:
        return "unused"

    def serialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {"tick": int(state["tick"])}

    def serialize_action(self, action: dict[str, Any]) -> dict[str, Any]:
        return {"kind": str(action.get("kind", ""))}

    def action_key(self, action: dict[str, Any]) -> str:
        return str(action.get("kind", ""))


class _NondeterministicObserveRuleSystem(_BaseRuleSystem):
    def observe(self, state: dict[str, Any], agent_id: str) -> dict[str, Any]:
        return {"tick": int(state["tick"]), "noise": random.random()}


class _UnstableSerializeStateRuleSystem(_BaseRuleSystem):
    def serialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {"tick": int(state["tick"]), "nonce": time.time_ns()}


class _InPlaceApplyRuleSystem(_BaseRuleSystem):
    def apply_action(self, state: dict[str, Any], agent_id: str, action: dict[str, Any]) -> TransitionResult:
        state["tick"] = int(state["tick"]) + 1
        return TransitionResult(next_state=state)


def _config() -> dict[str, Any]:
    return {
        "schema_version": "rulesim_v0",
        "rulesystem_id": "loop",
        "run_seed": 1,
        "episodes": 1,
        "max_steps": 3,
        "agents": [{"id": "agent_0", "strategy": "random_uniform", "params": {}}],
        "scenario": {"turn_order": ["agent_0"]},
        "artifact_policy": "none",
        "enforce_contract_checks": True,
    }


def test_live_path_rejects_nondeterministic_observe(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("orket.rulesim.workload.build_toy_rulesystem", lambda _rid: _NondeterministicObserveRuleSystem())
    with pytest.raises(ValueError, match="observe is non-deterministic"):
        run_rulesim_v0_sync(input_config=_config(), workspace_path=tmp_path)


def test_live_path_rejects_unstable_serialize_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("orket.rulesim.workload.build_toy_rulesystem", lambda _rid: _UnstableSerializeStateRuleSystem())
    with pytest.raises(ValueError, match="serialize_state is non-deterministic"):
        run_rulesim_v0_sync(input_config=_config(), workspace_path=tmp_path)


def test_live_path_rejects_in_place_apply_action(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("orket.rulesim.workload.build_toy_rulesystem", lambda _rid: _InPlaceApplyRuleSystem())
    with pytest.raises(ValueError, match="apply_action mutated input state in place|returned the input state object"):
        run_rulesim_v0_sync(input_config=_config(), workspace_path=tmp_path)

