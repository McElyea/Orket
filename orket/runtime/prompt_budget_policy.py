from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


DEFAULT_PROMPT_BUDGET_PATH = Path("core/policies/prompt_budget.yaml")
_VALID_STAGES = {"planner", "executor", "reviewer"}
_STAGE_KEYS = {"max_tokens", "protocol_tokens", "tool_schema_tokens", "task_tokens"}
_ROLE_STAGE_MAP = {
    "requirements_analyst": "planner",
    "architect": "planner",
    "lead_architect": "planner",
    "coder": "executor",
    "developer": "executor",
    "code_reviewer": "reviewer",
    "integrity_guard": "reviewer",
}


def load_prompt_budget_policy(path: Path | str = DEFAULT_PROMPT_BUDGET_PATH) -> dict[str, Any]:
    raw = _load_yaml_dict(Path(path))
    schema_version = str(raw.get("schema_version") or "").strip()
    budget_policy_version = str(raw.get("budget_policy_version") or "").strip()
    if not schema_version:
        raise ValueError("prompt_budget_policy:schema_version_required")
    if not budget_policy_version:
        raise ValueError("prompt_budget_policy:budget_policy_version_required")

    stages_raw = raw.get("stages")
    if not isinstance(stages_raw, dict) or not stages_raw:
        raise ValueError("prompt_budget_policy:stages_required")

    stages: dict[str, dict[str, int]] = {}
    for stage_name in sorted(stages_raw.keys()):
        normalized_stage = str(stage_name or "").strip().lower()
        if normalized_stage not in _VALID_STAGES:
            raise ValueError(f"prompt_budget_policy:unsupported_stage:{normalized_stage}")
        stage_payload = stages_raw.get(stage_name)
        if not isinstance(stage_payload, dict):
            raise ValueError(f"prompt_budget_policy:stage_payload_invalid:{normalized_stage}")
        missing = sorted(key for key in _STAGE_KEYS if key not in stage_payload)
        if missing:
            raise ValueError(f"prompt_budget_policy:stage_missing_fields:{normalized_stage}:{','.join(missing)}")
        normalized_limits: dict[str, int] = {}
        for key in sorted(_STAGE_KEYS):
            value = stage_payload.get(key)
            if not isinstance(value, int) or value <= 0:
                raise ValueError(f"prompt_budget_policy:stage_invalid_field:{normalized_stage}:{key}")
            normalized_limits[key] = int(value)
        component_sum = (
            normalized_limits["protocol_tokens"]
            + normalized_limits["tool_schema_tokens"]
            + normalized_limits["task_tokens"]
        )
        if component_sum < normalized_limits["max_tokens"]:
            raise ValueError(
                f"prompt_budget_policy:stage_component_coverage:{normalized_stage}:{component_sum}<max_tokens"
            )
        stages[normalized_stage] = normalized_limits

    for required_stage in sorted(_VALID_STAGES):
        if required_stage not in stages:
            raise ValueError(f"prompt_budget_policy:missing_stage:{required_stage}")

    return {
        "schema_version": schema_version,
        "budget_policy_version": budget_policy_version,
        "stages": stages,
    }


def resolve_prompt_stage(context: dict[str, Any]) -> str:
    explicit = str(context.get("prompt_stage") or "").strip().lower()
    if explicit in _VALID_STAGES:
        return explicit
    role = str(context.get("role") or "").strip().lower()
    return _ROLE_STAGE_MAP.get(role, "executor")


def _load_yaml_dict(path: Path) -> dict[str, Any]:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"prompt_budget_policy:read_error:{path}:{exc}") from exc
    try:
        payload = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ValueError(f"prompt_budget_policy:parse_error:{path}:{exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"prompt_budget_policy:schema_error:{path}:root")
    return dict(payload)
