from __future__ import annotations

import json
from typing import Any

from .turn_artifact_destination import TurnArtifactDestination


def write_prompt_budget_artifacts(
    *,
    destination: TurnArtifactDestination,
    prompt_budget_usage_json: str,
    prompt_structure_json: str,
    prompt_structure: dict[str, Any],
) -> None:
    out_dir = destination.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    destination.file_path("prompt_budget_usage.json").write_text(prompt_budget_usage_json, encoding="utf-8")
    destination.file_path("prompt_structure.json").write_text(prompt_structure_json, encoding="utf-8")

    previous_structure = _load_previous_prompt_structure(destination)
    if not isinstance(previous_structure, dict):
        return
    diff_lines = _prompt_structure_diff_lines(previous_structure, prompt_structure)
    if not diff_lines:
        return
    destination.file_path("prompt_diff.txt").write_text("\n".join(diff_lines) + "\n", encoding="utf-8")


def _load_previous_prompt_structure(
    destination: TurnArtifactDestination,
) -> dict[str, Any] | None:
    if destination.turn_index <= 1:
        return None
    previous_dir = destination.output_dir_for_turn(destination.turn_index - 1)
    path = previous_dir / "prompt_structure.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return dict(payload)


def _prompt_structure_diff_lines(previous: dict[str, Any], current: dict[str, Any]) -> list[str]:
    keys = (
        "prompt_stage",
        "prompt_template_version",
        "tokenizer_id",
        "tokenizer_source",
        "budget_policy_version",
        "message_count",
        "prompt_hash",
    )
    rows: list[str] = []
    for key in keys:
        before = previous.get(key)
        after = current.get(key)
        if before == after:
            continue
        rows.append(f"{key}: {before!r} -> {after!r}")
    return rows
