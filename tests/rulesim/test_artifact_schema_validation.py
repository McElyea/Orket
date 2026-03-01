from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from orket.rulesim.workload import run_rulesim_v0_sync

_TERMINAL_REASONS = {"win", "draw", "cycle_detected", "deadlock", "timeout", "invalid_action"}

RUN_SCHEMA = {
    "type": "object",
    "required": ["schema_version", "rulesystem_id", "run_id", "run_digest", "episodes", "max_steps"],
    "properties": {
        "schema_version": {"type": "string"},
        "rulesystem_id": {"type": "string"},
        "run_id": {"type": "string"},
        "run_digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "episodes": {"type": "integer", "minimum": 0},
        "max_steps": {"type": "integer", "minimum": 1},
    },
}

SUMMARY_SCHEMA = {
    "type": "object",
    "required": ["episodes", "win_rate", "terminal_reason_distribution", "top_findings"],
    "properties": {
        "episodes": {"type": "integer", "minimum": 0},
        "win_rate": {"type": "object"},
        "terminal_reason_distribution": {"type": "object"},
        "top_findings": {"type": "array"},
    },
}

EPISODE_SCHEMA = {
    "type": "object",
    "required": ["episode_id", "terminal_result", "step_index", "anomalies"],
    "properties": {
        "episode_id": {"type": "string"},
        "step_index": {"type": "integer", "minimum": 0},
        "anomalies": {"type": "array"},
        "terminal_result": {
            "type": "object",
            "required": ["reason", "winners", "scores"],
            "properties": {
                "reason": {"type": "string"},
                "winners": {"type": "array"},
                "scores": {},
            },
        },
    },
}

SUSPICIOUS_SCHEMA = {
    "type": "object",
    "required": ["episodes"],
    "properties": {
        "episodes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["episode_id", "type", "step_index"],
                "properties": {
                    "episode_id": {"type": "string"},
                    "type": {"type": "string"},
                    "step_index": {"type": "integer", "minimum": 0},
                },
            },
        }
    },
}


def test_artifact_files_conform_to_schema_and_references(tmp_path: Path) -> None:
    result = run_rulesim_v0_sync(
        input_config={
            "schema_version": "rulesim_v0",
            "rulesystem_id": "illegal_action",
            "run_seed": 21,
            "episodes": 10,
            "max_steps": 5,
            "agents": [
                {"id": "agent_0", "strategy": "scripted", "params": {"sequence": [{"kind": "illegal_move"}]}},
            ],
            "scenario": {"turn_order": ["agent_0"]},
            "illegal_action_policy": "substitute_first",
            "artifact_policy": "all",
        },
        workspace_path=tmp_path,
    )
    root = Path(result["artifact_root"])
    run_payload = json.loads((root / "run.json").read_text(encoding="utf-8"))
    summary_payload = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    suspicious_payload = json.loads((root / "suspicious" / "index.json").read_text(encoding="utf-8"))
    jsonschema.validate(run_payload, RUN_SCHEMA)
    jsonschema.validate(summary_payload, SUMMARY_SCHEMA)
    jsonschema.validate(suspicious_payload, SUSPICIOUS_SCHEMA)
    for reason in summary_payload["terminal_reason_distribution"].keys():
        assert reason in _TERMINAL_REASONS
    for episode_ref in suspicious_payload["episodes"]:
        episode_file = root / "episodes" / str(episode_ref["episode_id"]) / "episode.json"
        assert episode_file.exists()
        episode_payload = json.loads(episode_file.read_text(encoding="utf-8"))
        jsonschema.validate(episode_payload, EPISODE_SCHEMA)
        assert episode_payload["terminal_result"]["reason"] in _TERMINAL_REASONS

