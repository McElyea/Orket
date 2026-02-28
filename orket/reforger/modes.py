from __future__ import annotations

from pathlib import Path

from .manifest import ModeSpec


class ModeValidationError(ValueError):
    """Deterministic mode validation error."""


def _require_str(payload: dict[str, object], key: str, path: Path) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ModeValidationError(f"Mode field '{key}' must be a non-empty string: {path}")
    return value.strip()


def _require_str_list(payload: dict[str, object], key: str, path: Path) -> tuple[str, ...]:
    value = payload.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ModeValidationError(f"Mode field '{key}' must be a list of non-empty strings: {path}")
    return tuple(item.strip() for item in value)


def load_mode(mode_path: Path) -> ModeSpec:
    if not mode_path.is_file():
        raise ModeValidationError(f"Mode file not found: {mode_path}")
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ModeValidationError("PyYAML is required to parse mode YAML files.") from exc
    try:
        payload = yaml.safe_load(mode_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ModeValidationError(f"Failed to parse mode YAML: {mode_path}") from exc
    if not isinstance(payload, dict):
        raise ModeValidationError(f"Mode file must contain a mapping/object: {mode_path}")

    mode_id = _require_str(payload, "mode_id", mode_path)
    description = _require_str(payload, "description", mode_path)
    hard_rules = _require_str_list(payload, "hard_rules", mode_path)
    soft_rules = _require_str_list(payload, "soft_rules", mode_path)
    required_outputs = _require_str_list(payload, "required_outputs", mode_path)
    suite_ref = _require_str(payload, "suite_ref", mode_path)

    rubric = payload.get("rubric")
    if not isinstance(rubric, dict):
        raise ModeValidationError(f"Mode field 'rubric' must be an object: {mode_path}")

    normalized_rubric = {str(k): rubric[k] for k in sorted(rubric)}
    return ModeSpec(
        mode_id=mode_id,
        description=description,
        hard_rules=hard_rules,
        soft_rules=soft_rules,
        required_outputs=required_outputs,
        suite_ref=suite_ref,
        rubric=normalized_rubric,
        path=mode_path.resolve(),
    )

