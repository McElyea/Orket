from __future__ import annotations

from pathlib import Path


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_skill_loader_error_schema_doc_contains_required_fields_and_codes() -> None:
    path = Path("docs/projects/archive/Skills/SKILL_LOADER_ERROR_SCHEMA.md")
    assert path.exists(), f"Missing schema doc: {path}"
    text = _read(path)

    required_tokens = [
        "skill.loader_error.v1",
        "error_code",
        "message",
        "skill_id",
        "skill_version",
        "skill_contract_version_seen",
        "validation_stage",
        "retryable",
        "entrypoint_id",
        "ERR_CONTRACT_INVALID",
        "ERR_SCHEMA_INVALID",
        "ERR_PERMISSION_UNDECLARED",
        "ERR_FINGERPRINT_INCOMPLETE",
        "ERR_RUNTIME_UNPINNED",
        "ERR_SIDE_EFFECT_UNDECLARED",
        "ERR_CONTRACT_UNSUPPORTED_VERSION",
        "ERR_VALIDATION_INTERNAL",
    ]
    missing = [token for token in required_tokens if token not in text]
    assert not missing, f"Missing required skill loader error schema tokens: {missing}"
