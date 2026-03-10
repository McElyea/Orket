from __future__ import annotations

from pathlib import Path

import pytest

from orket.runtime.runtime_invariant_registry import runtime_invariant_registry_snapshot


# Layer: unit
def test_runtime_invariant_registry_snapshot_parses_invariants_from_doc(tmp_path: Path) -> None:
    doc = tmp_path / "RUNTIME_INVARIANTS.md"
    doc.write_text(
        "# Runtime Invariants\n\n1. `INV-001`: First invariant.\n2. `INV-002`: Second invariant.\n",
        encoding="utf-8",
    )
    payload = runtime_invariant_registry_snapshot(doc_path=doc)
    assert payload["schema_version"] == "1.0"
    assert [row["invariant_id"] for row in payload["invariants"]] == ["INV-001", "INV-002"]


# Layer: contract
def test_runtime_invariant_registry_snapshot_rejects_empty_registry(tmp_path: Path) -> None:
    doc = tmp_path / "RUNTIME_INVARIANTS.md"
    doc.write_text("# Runtime Invariants\n\nNo invariant lines.\n", encoding="utf-8")
    with pytest.raises(ValueError, match="E_RUNTIME_INVARIANT_REGISTRY_EMPTY"):
        _ = runtime_invariant_registry_snapshot(doc_path=doc)


# Layer: contract
def test_runtime_invariant_registry_snapshot_reads_default_authority_doc() -> None:
    payload = runtime_invariant_registry_snapshot()
    invariant_ids = {row["invariant_id"] for row in payload["invariants"]}
    assert "INV-001" in invariant_ids
