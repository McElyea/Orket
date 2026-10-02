"""Contract: public canonical bytes, numeric admission and diagnostic differences."""
import json
import sys
from copy import deepcopy

import pytest

from orket.kernel.v1 import canonical

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("value", [
    canonical.JS_SAFE_INT_MAX + 1, canonical.JS_SAFE_INT_MIN - 1, b"bytes", {"not-json"}, object(),
])
def test_strict_public_canonicalization_refuses_out_of_domain_nested_values(value):
    with pytest.raises(canonical.CanonicalizationError):
        canonical.canonical_json_bytes({"nested": [value]})


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_float_opt_in_still_refuses_nonfinite_numbers(value):
    with pytest.raises(canonical.CanonicalizationError, match="Non-finite number"):
        canonical.canonical_json_bytes({"metric": value}, allow_float=True)


def test_installed_backend_retains_utf16_key_order_and_safe_scalar_values():
    value = {"\uffff": 1, "\U0001f600": 2}
    assert canonical.canonical_json_bytes(value) == '{"\U0001f600":2,"\uffff":1}'.encode()
    assert canonical.canonical_json_bytes([None, True, False, canonical.JS_SAFE_INT_MAX]) == (
        b"[null,true,false,9007199254740991]"
    )
    assert canonical.canonical_json_bytes({"metric": 0.5}, allow_float=True) == b'{"metric":0.5}'


def test_controlled_missing_dependencies_refuse_unless_legacy_fallback_is_explicit(monkeypatch):
    """Contract: import-system fault injection; not a naturally missing host dependency."""
    monkeypatch.setitem(sys.modules, "rfc8785", None)
    monkeypatch.setitem(sys.modules, "jcs", None)
    payload = {"z": 2, "a": 1}
    with pytest.raises(canonical.CanonicalizationError, match="No RFC 8785 canonicalizer installed"):
        canonical.canonical_json_bytes(payload)
    assert canonical.canonical_json_bytes(payload, allow_non_rfc8785_fallback=True) == b'{"a":1,"z":2}'


def test_turn_digest_excludes_diagnostics_but_keeps_contract_failure_identity():
    first = {"outcome": "FAIL", "events": ["first event"], "turn_result_digest": "old",
             "issues": [None, {"code": "E_FAIL", "message": "first diagnostic"}]}
    before = deepcopy(first)
    second = deepcopy(first)
    second.update(events=["other event"], turn_result_digest="replacement")
    second["issues"][1]["message"] = "other diagnostic"
    assert canonical.compute_turn_result_digest(first) == canonical.compute_turn_result_digest(second)
    assert first == before and canonical.normalized_turn_result_surface(first)["issues"][0] is None
    second["issues"][1]["code"] = "E_DIFFERENT"
    assert canonical.compute_turn_result_digest(first) != canonical.compute_turn_result_digest(second)
    assert canonical.normalized_turn_result_surface({"issues": None, "events": []}) == {"issues": None}


def test_domain_policy_keeps_raw_order_distinct_from_canonical_equivalence():
    first = {"timestamp": "first", "nodes": [{"id": "b"}, {"id": "a"}], "message": "a\r\nb\rc"}
    second = {"message": "a\nb\nc", "nodes": [{"id": "a"}, {"id": "b"}], "timestamp": "second"}
    before = deepcopy(first)
    assert canonical.odr_canonical_json_bytes(first) == canonical.odr_canonical_json_bytes(second)
    assert canonical.odr_raw_signature(first) != canonical.odr_raw_signature(second)
    assert first == before
    policy = canonical.CanonicalPolicy(normalize_strings=False)
    assert policy.normalize({"message": "a\r\nb"}) == {"message": "a\r\nb"}
    assert policy.digest({"count": 1}) == canonical.structural_digest(b'{"count":1}')
    assert canonical.sorted_deterministically(iter([2, 10, 1])) == [1, 10, 2]
    assert canonical.fs_token("a%/b\\c:d") == "a%25%2Fb%5Cc%3Ad"


@pytest.mark.parametrize("left,right,expected", [
    ({"a": {"b": 1}}, {"a": {"b": "1"}}, "$/a/b"),
    ({"a/b~c": 1}, {}, "$/a~1b~0c"),
    ({"a": 1, "z": 2}, {"a": 1, "z": 3}, "$/z"),
    ({"items": [1, 2]}, {"items": [1, 3]}, "$/items/1"),
    ({"items": [1]}, {"items": [1, 2]}, "$/items"),
    ({"items": []}, {"items": {}}, "$/items"),
    ({"same": [1]}, {"same": [1]}, "$"),
])
def test_public_difference_path_identifies_nested_type_length_and_key_changes(left, right, expected):
    assert canonical.first_diff_path(json.dumps(left).encode(), json.dumps(right).encode()) == expected


@pytest.mark.parametrize("invalid", [b"\xff", b"{", b"not-json"])
def test_unparseable_difference_inputs_report_only_root(invalid):
    assert canonical.first_diff_path(invalid, b"{}") == "$"
