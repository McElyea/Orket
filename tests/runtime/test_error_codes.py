from __future__ import annotations

from orket.runtime.error_codes import (
    EXTRANEOUS_TEXT,
    SCHEMA_MISMATCH,
    all_error_families,
    all_error_leaf_codes,
    error_family_for_leaf,
    error_registry_snapshot,
)


def test_error_registry_snapshot_has_expected_shape() -> None:
    snapshot = error_registry_snapshot()
    assert snapshot["schema_version"] == "local_prompt_error_registry.v1"
    assert isinstance(snapshot["families"], list)
    assert isinstance(snapshot["leaf_mappings"], list)


def test_error_family_lookup_for_known_leaf_codes() -> None:
    assert error_family_for_leaf("ERR_JSON_MD_FENCE") == EXTRANEOUS_TEXT
    assert error_family_for_leaf("ERR_SCHEMA_EXTRA_KEYS") == SCHEMA_MISMATCH
    assert error_family_for_leaf("MISSING") == ""


def test_error_registry_lists_are_stable() -> None:
    families = all_error_families()
    leaves = all_error_leaf_codes()
    assert "EXTRANEOUS_TEXT" in families
    assert "SCHEMA_MISMATCH" in families
    assert "ERR_JSON_MD_FENCE" in leaves
