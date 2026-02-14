from __future__ import annotations

from orket.core.domain.guard_rule_catalog import (
    DEFAULT_GUARD_RULE_IDS,
    normalize_rule_ids,
    ownership_conflicts,
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
