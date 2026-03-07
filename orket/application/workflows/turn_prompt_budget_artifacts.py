from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orket.utils import sanitize_name


def write_prompt_budget_artifacts(
    *,
    workspace: Path,
    session_id: str,
    issue_id: str,
    role_name: str,
    turn_index: int,
    prompt_budget_usage: dict[str, Any],
    prompt_structure: dict[str, Any],
) -> None:
    out_dir = _turn_output_dir(
        workspace=workspace,
        session_id=session_id,
        issue_id=issue_id,
        role_name=role_name,
        turn_index=turn_index,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "prompt_budget_usage.json").write_text(
        json.dumps(prompt_budget_usage, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (out_dir / "prompt_structure.json").write_text(
        json.dumps(prompt_structure, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    previous_structure = _load_previous_prompt_structure(
        workspace=workspace,
        session_id=session_id,
        issue_id=issue_id,
        role_name=role_name,
        turn_index=turn_index,
    )
    if not isinstance(previous_structure, dict):
        return
    diff_lines = _prompt_structure_diff_lines(previous_structure, prompt_structure)
    if not diff_lines:
        return
    (out_dir / "prompt_diff.txt").write_text("\n".join(diff_lines) + "\n", encoding="utf-8")


def _turn_output_dir(
    *,
    workspace: Path,
    session_id: str,
    issue_id: str,
    role_name: str,
    turn_index: int,
) -> Path:
    return (
        workspace
        / "observability"
        / sanitize_name(session_id)
        / sanitize_name(issue_id)
        / f"{turn_index:03d}_{sanitize_name(role_name)}"
    )


def _load_previous_prompt_structure(
    *,
    workspace: Path,
    session_id: str,
    issue_id: str,
    role_name: str,
    turn_index: int,
) -> dict[str, Any] | None:
    if turn_index <= 1:
        return None
    previous_dir = _turn_output_dir(
        workspace=workspace,
        session_id=session_id,
        issue_id=issue_id,
        role_name=role_name,
        turn_index=turn_index - 1,
    )
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
