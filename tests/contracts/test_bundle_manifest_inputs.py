"""Layer: contract. Pure manifest admission consumes supplied values only."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.adapters.storage.bundle_store import safe_archive_name
from orket.core.domain.orket_manifest import OrketManifest, is_engine_compatible, resolve_model_selection

pytestmark = pytest.mark.contract


def test_identical_manifest_inputs_have_identical_policy_results() -> None:
    raw = Path("tests/fixtures/orket_manifest/valid_minimal.json").read_text(encoding="utf-8")
    one, two = (OrketManifest.model_validate(json.loads(raw)) for _ in range(2))
    assert one == two
    assert is_engine_compatible(one, "0.6.24") == is_engine_compatible(two, "0.6.24")
    options = {"available_models": ["llama3.2:3b", "qwen2.5-coder:3b"]}
    assert resolve_model_selection(one, **options) == resolve_model_selection(two, **options)


def test_safe_archive_name_rejects_path_traversal() -> None:
    assert safe_archive_name("agents/reader.json") is True
    assert safe_archive_name("../escape.txt") is False
    assert safe_archive_name("/absolute.txt") is False
    assert safe_archive_name("nested//double/slash.txt") is False
