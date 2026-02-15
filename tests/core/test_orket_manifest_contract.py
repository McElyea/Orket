from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from orket.core.domain.orket_manifest import (
    OrketManifest,
    is_engine_compatible,
    load_orket_manifest,
    resolve_model_selection,
)


def _fixture_path(name: str) -> Path:
    return Path("tests") / "fixtures" / "orket_manifest" / name


def _load_fixture_payload(name: str) -> dict:
    return json.loads(_fixture_path(name).read_text(encoding="utf-8"))


def test_valid_manifest_fixture_passes() -> None:
    manifest = load_orket_manifest(_fixture_path("valid_minimal.json"))
    assert manifest.apiVersion == "orket.io/v1"
    assert manifest.kind == "Orket"
    assert manifest.metadata.engineVersion == ">=0.3.0,<0.6.0"
    assert manifest.guards[0].value == "hallucination"


def test_missing_required_section_permissions_fails() -> None:
    payload = _load_fixture_payload("invalid_missing_permissions.json")
    with pytest.raises(ValidationError) as exc:
        OrketManifest.model_validate(payload)
    first = exc.value.errors()[0]
    assert tuple(first["loc"]) == ("permissions",)
    assert first["type"] == "missing"


def test_invalid_guard_enum_value_fails() -> None:
    payload = _load_fixture_payload("invalid_guard_enum.json")
    with pytest.raises(ValidationError) as exc:
        OrketManifest.model_validate(payload)
    errors = exc.value.errors()
    assert any(tuple(err["loc"]) == ("guards", 1) for err in errors)
    assert any(err["type"] == "enum" for err in errors)


def test_invalid_engine_version_specifier_fails() -> None:
    payload = _load_fixture_payload("invalid_engine_version.json")
    with pytest.raises(ValidationError) as exc:
        OrketManifest.model_validate(payload)
    errors = exc.value.errors()
    assert any(tuple(err["loc"]) == ("metadata", "engineVersion") for err in errors)
    assert any("parseable as a version specifier" in err["msg"] for err in errors)


def test_engine_compatibility_check() -> None:
    manifest = load_orket_manifest(_fixture_path("valid_minimal.json"))
    assert is_engine_compatible(manifest, "0.3.9") is True
    assert is_engine_compatible(manifest, "0.9.0") is False


def test_model_selection_prefers_manifest_candidates() -> None:
    manifest = load_orket_manifest(_fixture_path("valid_minimal.json"))
    result = resolve_model_selection(
        manifest,
        available_models=["qwen2.5-coder:3b", "llama3.2:3b"],
        model_override="",
    )
    assert result["ok"] is True
    assert result["selected_model"] == "qwen2.5-coder:3b"


def test_model_selection_rejects_disallowed_override() -> None:
    manifest_payload = _load_fixture_payload("valid_minimal.json")
    manifest_payload["model"]["allowOverride"] = False
    manifest = OrketManifest.model_validate(manifest_payload)
    result = resolve_model_selection(
        manifest,
        available_models=["qwen2.5-coder:7b"],
        model_override="qwen2.5-coder:7b",
    )
    assert result["ok"] is False
    assert result["code"] == "E_MODEL_OVERRIDE_NOT_ALLOWED"
