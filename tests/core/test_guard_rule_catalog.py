from __future__ import annotations

import pytest

from orket.core.domain.guard_rule_catalog import (
    DEFAULT_GUARD_RULE_REGISTRY,
    DEFAULT_GUARD_RULE_IDS,
    GuardRule,
    build_guard_rule_registry,
    normalize_rule_ids,
    ownership_conflicts,
    prompt_guard_namespace_conflicts,
    resolve_runtime_guard_rule_ids,
    validate_runtime_guard_rule_ids,
)


def test_normalize_rule_ids_deduplicates_and_trims():
    values = [" A ", "B", "", "A", None]
    assert normalize_rule_ids(values) == ["A", "B"]


def test_ownership_conflicts_returns_sorted_intersection():
    prompt = ["X", "Y", "Z"]
    runtime = ["A", "Y", "X"]
    assert ownership_conflicts(prompt, runtime) == ["X", "Y"]


def test_default_guard_rule_catalog_contains_core_rules():
    assert "HALLUCINATION.FILE_NOT_FOUND" in DEFAULT_GUARD_RULE_IDS
    assert "SECURITY.PATH_TRAVERSAL" in DEFAULT_GUARD_RULE_IDS
    assert "CONSISTENCY.OUTPUT_FORMAT" in DEFAULT_GUARD_RULE_IDS


def test_default_guard_registry_contains_all_default_ids():
    assert sorted(DEFAULT_GUARD_RULE_REGISTRY.keys()) == sorted(DEFAULT_GUARD_RULE_IDS)


def test_build_guard_rule_registry_rejects_duplicate_rule_ids():
    with pytest.raises(ValueError, match="duplicate guard rule_id"):
        build_guard_rule_registry(
            [
                GuardRule(
                    rule_id="HALLUCINATION.FILE_NOT_FOUND",
                    owner="hallucination",
                    description="x",
                    severity="strict",
                    scope=("output",),
                ),
                GuardRule(
                    rule_id="HALLUCINATION.FILE_NOT_FOUND",
                    owner="hallucination",
                    description="y",
                    severity="strict",
                    scope=("output",),
                ),
            ]
        )


def test_build_guard_rule_registry_rejects_owner_prefix_mismatch():
    with pytest.raises(ValueError, match="must use prefix"):
        build_guard_rule_registry(
            [
                GuardRule(
                    rule_id="SECURITY.FILE_NOT_FOUND",
                    owner="hallucination",
                    description="x",
                    severity="strict",
                    scope=("output",),
                )
            ]
        )


def test_validate_runtime_guard_rule_ids_rejects_unknown_values():
    with pytest.raises(ValueError, match="Unknown runtime guard rule_id values"):
        validate_runtime_guard_rule_ids(["HALLUCINATION.FILE_NOT_FOUND", "UNKNOWN.RULE"])


def test_validate_runtime_guard_rule_ids_rejects_duplicates():
    with pytest.raises(ValueError, match="Duplicate runtime guard rule_id values"):
        validate_runtime_guard_rule_ids(
            ["HALLUCINATION.FILE_NOT_FOUND", "HALLUCINATION.FILE_NOT_FOUND"]
        )


def test_resolve_runtime_guard_rule_ids_returns_defaults_when_unset_or_empty():
    assert resolve_runtime_guard_rule_ids(None) == DEFAULT_GUARD_RULE_IDS
    assert resolve_runtime_guard_rule_ids([]) == DEFAULT_GUARD_RULE_IDS


def test_prompt_guard_namespace_conflicts_detects_reserved_prefixes():
    conflicts = prompt_guard_namespace_conflicts(["STYLE.001", "HALLUCINATION.INVENTED_DETAIL"])
    assert conflicts == ["HALLUCINATION.INVENTED_DETAIL"]
