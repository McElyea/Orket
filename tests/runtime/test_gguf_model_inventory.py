from __future__ import annotations

from pathlib import Path

from orket.runtime.config.gguf_model_inventory import (
    alias_from_gguf_path,
    inventory_gguf_models,
    is_gguf_path_inside_root,
)


# Layer: contract
def test_gguf_inventory_records_files_under_configured_root(tmp_path: Path) -> None:
    model_root = tmp_path / "models"
    model_root.mkdir()
    model_file = model_root / "Qwen3.6-27B-Q4_K_M.gguf"
    model_file.write_bytes(b"gguf")

    payload = inventory_gguf_models(model_root=model_root)

    assert payload.status == "OK"
    assert payload.records[0].alias == "qwen3.6-27b-q4_k_m"
    assert payload.records[0].size_bytes == 4
    assert payload.records[0].digest_status == "pending"


# Layer: contract
def test_gguf_inventory_empty_root_blocks(tmp_path: Path) -> None:
    model_root = tmp_path / "empty"
    model_root.mkdir()

    payload = inventory_gguf_models(model_root=model_root)

    assert payload.status == "BLOCKED"
    assert payload.error == "empty_inventory"
    assert payload.records == ()


# Layer: contract
def test_gguf_inventory_uses_path_containment_check(tmp_path: Path) -> None:
    model_root = tmp_path / "models"
    outside = tmp_path / "outside.gguf"
    model_root.mkdir()
    outside.write_bytes(b"outside")

    assert is_gguf_path_inside_root(root=model_root, candidate=outside) is False


# Layer: contract
def test_gguf_inventory_digest_states_are_explicit(tmp_path: Path) -> None:
    model_root = tmp_path / "models"
    model_root.mkdir()
    model_file = model_root / "A.gguf"
    model_file.write_bytes(b"gguf")

    skipped = inventory_gguf_models(model_root=model_root, digest_policy="skipped_by_policy")
    computed = inventory_gguf_models(
        model_root=model_root,
        digest_status_by_alias={"a": "computed"},
        sha256_by_alias={"a": "abc123"},
    )
    failed = inventory_gguf_models(model_root=model_root, digest_status_by_alias={"a": "failed"})
    missing = inventory_gguf_models(model_root=model_root, expected_aliases=("missing",))

    assert skipped.records[0].digest_status == "skipped_by_policy"
    assert computed.records[0].digest_status == "computed"
    assert computed.records[0].sha256 == "abc123"
    assert failed.records[0].digest_status == "failed"
    assert {record.digest_status for record in missing.records} == {"pending", "missing"}


# Layer: unit
def test_alias_from_gguf_path_uses_lowercase_stem() -> None:
    assert alias_from_gguf_path("Qwen3.6-27B-Q4_K_M.gguf") == "qwen3.6-27b-q4_k_m"

