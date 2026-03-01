from __future__ import annotations

import pytest

from orket.rulesim.canonical import StateSerializationError, canonical_json, hash_state


def test_canonical_json_sorts_keys_and_compacts() -> None:
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_canonical_json_normalizes_floats() -> None:
    assert canonical_json({"value": 1.23456789}) == '{"value":1.23457}'


def test_hash_state_is_stable() -> None:
    state = {"k": [1, 2, 3], "f": 1.23456789}
    assert hash_state(state) == hash_state(state)


def test_non_serializable_error_has_path() -> None:
    with pytest.raises(StateSerializationError) as exc:
        canonical_json({"x": object()})
    assert 'value["x"]' in str(exc.value)
