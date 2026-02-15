from __future__ import annotations

import json
from pathlib import Path

from orket.application.services.tool_parser import ToolParser


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_dialect_versions_match_pinned_contract():
    contract_path = Path("model") / "core" / "contracts" / "dialect_version_contract.json"
    contract = _load_json(contract_path)
    dialects = contract.get("dialects", {})
    assert isinstance(dialects, dict) and dialects

    dialect_dir = Path("model") / "core" / "dialects"
    errors: list[str] = []
    for dialect_name, details in dialects.items():
        dialect_path = dialect_dir / f"{dialect_name}.json"
        if not dialect_path.exists():
            errors.append(f"Missing dialect asset: {dialect_path}")
            continue
        payload = _load_json(dialect_path)
        pinned_version = str((details or {}).get("version") or "").strip()
        actual_version = str((payload.get("prompt_metadata") or {}).get("version") or "").strip()
        if pinned_version != actual_version:
            errors.append(
                f"{dialect_path}: pinned version {pinned_version!r} does not match actual {actual_version!r}"
            )
    assert not errors, "\n".join(errors)


def test_dialect_parser_fixtures_pass_for_each_model_family():
    contract_path = Path("model") / "core" / "contracts" / "dialect_version_contract.json"
    contract = _load_json(contract_path)
    dialects = contract.get("dialects", {})
    assert isinstance(dialects, dict) and dialects

    errors: list[str] = []
    for dialect_name, details in dialects.items():
        fixtures = (details or {}).get("parser_fixtures") or []
        if not isinstance(fixtures, list) or not fixtures:
            errors.append(f"{dialect_name}: parser_fixtures must be a non-empty list.")
            continue
        for idx, fixture in enumerate(fixtures):
            if not isinstance(fixture, dict):
                errors.append(f"{dialect_name}: parser_fixtures[{idx}] must be an object.")
                continue
            text = str(fixture.get("input") or "")
            expected_tool = str(fixture.get("expected_tool") or "")
            expected_arg_keys = fixture.get("expected_arg_keys") or []
            parsed = ToolParser.parse(text)
            if not parsed:
                errors.append(f"{dialect_name}: parser fixture {idx} did not parse any tool calls.")
                continue
            tool = parsed[0]
            if tool.get("tool") != expected_tool:
                errors.append(
                    f"{dialect_name}: parser fixture {idx} expected tool {expected_tool!r}, got {tool.get('tool')!r}."
                )
            args = tool.get("args", {})
            for arg_key in expected_arg_keys:
                if str(arg_key) not in args:
                    errors.append(f"{dialect_name}: parser fixture {idx} missing arg key {arg_key!r}.")
    assert not errors, "\n".join(errors)
