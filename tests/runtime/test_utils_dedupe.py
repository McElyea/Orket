from __future__ import annotations

from orket.utils import dedupe_ordered


def test_dedupe_ordered_trims_and_preserves_first_seen_order() -> None:
    """Layer: unit. Verifies the shared ordered de-duplication utility."""
    assert dedupe_ordered([" a ", "", "b", "a", None, " b "]) == ["a", "b"]
