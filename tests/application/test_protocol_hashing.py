from __future__ import annotations

import math

import pytest

from orket.runtime.registry.protocol_hashing import (
    ProtocolCanonicalizationError,
    build_step_id,
    canonical_json,
    default_protocol_hash,
    default_tool_schema_hash,
    derive_operation_id,
    derive_step_seed,
    hash_env_allowlist,
    hash_framed_fields,
)


def test_canonical_json_is_stable_for_equivalent_objects() -> None:
    left = {"b": [3, 2, 1], "a": {"z": 1, "x": 2}}
    right = {"a": {"x": 2, "z": 1}, "b": [3, 2, 1]}
    assert canonical_json(left) == canonical_json(right)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_canonical_json_rejects_non_finite_numbers(value: float) -> None:
    with pytest.raises(ProtocolCanonicalizationError):
        canonical_json({"value": value})


def test_hash_framed_fields_uses_kind_as_domain_separator() -> None:
    fields = ["run-1", "ISSUE-1:1", 0]
    first = hash_framed_fields("operation_id", fields)
    second = hash_framed_fields("step_seed", fields)
    assert first != second


def test_derived_operation_id_is_stable() -> None:
    step_id = build_step_id(issue_id="ISSUE-1", turn_index=2)
    first = derive_operation_id(run_id="run-1", step_id=step_id, tool_index=0)
    second = derive_operation_id(run_id="run-1", step_id=step_id, tool_index=0)
    assert first == second
    assert len(first) == 64


def test_derived_step_seed_changes_when_step_id_changes() -> None:
    first = derive_step_seed(run_seed="seed-a", run_id="run-1", step_id="ISSUE-1:1")
    second = derive_step_seed(run_seed="seed-a", run_id="run-1", step_id="ISSUE-1:2")
    assert first != second


def test_default_hashes_are_64_char_hex() -> None:
    assert len(default_protocol_hash()) == 64
    assert len(default_tool_schema_hash()) == 64


def test_hash_env_allowlist_normalizes_key_order() -> None:
    left = hash_env_allowlist({"B": "2", "A": "1"})
    right = hash_env_allowlist({"A": "1", "B": "2"})
    assert left == right
