from __future__ import annotations

from orket.core.domain.verification_scope import (
    build_verification_scope,
    parse_verification_scope,
)


def test_build_verification_scope_normalizes_and_deduplicates_values():
    scope = build_verification_scope(
        workspace=[" b.py ", "a.py", "a.py", ""],
        provided_context=["ctx-2", "ctx-1", None],
        declared_interfaces=[" write_file ", "read_file", "write_file"],
        strict_grounding=True,
        forbidden_phrases=["foo", " foo "],
        enforce_path_hardening=True,
        consistency_tool_calls_only=True,
    )
    assert scope["workspace"] == ["a.py", "b.py"]
    assert scope["provided_context"] == ["ctx-1", "ctx-2"]
    assert scope["declared_interfaces"] == ["read_file", "write_file"]
    assert scope["forbidden_phrases"] == ["foo"]
    assert scope["strict_grounding"] is True
    assert scope["enforce_path_hardening"] is True
    assert scope["consistency_tool_calls_only"] is True


def test_parse_verification_scope_returns_none_for_non_dict():
    assert parse_verification_scope(None) is None
    assert parse_verification_scope([]) is None


def test_parse_verification_scope_applies_defaults_and_normalization():
    scope = parse_verification_scope({"workspace": ["x.py", " x.py "]})
    assert scope == {
        "workspace": ["x.py"],
        "provided_context": [],
        "declared_interfaces": [],
        "strict_grounding": False,
        "forbidden_phrases": [],
        "enforce_path_hardening": True,
        "consistency_tool_calls_only": False,
    }
