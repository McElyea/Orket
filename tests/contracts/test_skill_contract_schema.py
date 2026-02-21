from __future__ import annotations

from pathlib import Path


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_skill_contract_schema_doc_exists_and_contains_required_tokens() -> None:
    path = Path("docs/specs/SKILL_CONTRACT_SCHEMA.md")
    assert path.exists(), f"Missing schema doc: {path}"
    text = _read(path)

    required_tokens = [
        "skill.contract.v1",
        "skill_contract_version",
        "skill_id",
        "skill_version",
        "manifest_digest",
        "entrypoints",
        "entrypoint_id",
        "runtime",
        "input_schema",
        "output_schema",
        "error_schema",
        "args_fingerprint_fields",
        "result_fingerprint_fields",
        "side_effect_fingerprint_fields",
        "requested_permissions",
        "required_permissions",
        "tool_profile_id",
        "tool_profile_version",
        "requested_determinism_profile",
        "determinism_eligible",
    ]
    missing = [token for token in required_tokens if token not in text]
    assert not missing, f"Missing required skill contract schema tokens: {missing}"

