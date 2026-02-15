from __future__ import annotations

from orket.core.domain.verification_scope import (
    build_verification_scope,
    parse_verification_scope,
)


def test_build_verification_scope_normalizes_and_deduplicates_values():
    scope = build_verification_scope(
        workspace=[" b.py ", "a.py", "a.py", ""],
        active_context=["ctx-2", "ctx-1", None],
        passive_context=["passive-2", "passive-1", "passive-1"],
        archived_context=["arch-1", "arch-1"],
        declared_interfaces=[" write_file ", "read_file", "write_file"],
        strict_grounding=True,
        forbidden_phrases=["foo", " foo "],
        enforce_path_hardening=True,
        consistency_tool_calls_only=True,
        max_workspace_items=10,
        max_active_context_items=5,
        max_passive_context_items=7,
        max_archived_context_items=9,
        max_total_context_items=12,
    )
    assert scope["workspace"] == ["a.py", "b.py"]
    assert scope["active_context"] == ["ctx-1", "ctx-2"]
    assert scope["provided_context"] == ["ctx-1", "ctx-2"]
    assert scope["passive_context"] == ["passive-1", "passive-2"]
    assert scope["archived_context"] == ["arch-1"]
    assert scope["declared_interfaces"] == ["read_file", "write_file"]
    assert scope["forbidden_phrases"] == ["foo"]
    assert scope["strict_grounding"] is True
    assert scope["enforce_path_hardening"] is True
    assert scope["consistency_tool_calls_only"] is True
    assert scope["max_workspace_items"] == 10
    assert scope["max_active_context_items"] == 5
    assert scope["max_passive_context_items"] == 7
    assert scope["max_archived_context_items"] == 9
    assert scope["max_total_context_items"] == 12


def test_parse_verification_scope_returns_none_for_non_dict():
    assert parse_verification_scope(None) is None
    assert parse_verification_scope([]) is None


def test_parse_verification_scope_applies_defaults_and_normalization():
    scope = parse_verification_scope({"workspace": ["x.py", " x.py "]})
    assert scope == {
        "workspace": ["x.py"],
        "provided_context": [],
        "active_context": [],
        "passive_context": [],
        "archived_context": [],
        "declared_interfaces": [],
        "strict_grounding": False,
        "forbidden_phrases": [],
        "enforce_path_hardening": True,
        "consistency_tool_calls_only": False,
        "max_workspace_items": None,
        "max_active_context_items": None,
        "max_passive_context_items": None,
        "max_archived_context_items": None,
        "max_total_context_items": None,
    }


def test_parse_verification_scope_backfills_active_from_provided_context():
    scope = parse_verification_scope({"provided_context": ["ctx-a", "ctx-b"]})
    assert scope["active_context"] == ["ctx-a", "ctx-b"]
    assert scope["provided_context"] == ["ctx-a", "ctx-b"]


def test_parse_verification_scope_normalizes_invalid_limits_to_none():
    scope = parse_verification_scope(
        {
            "max_workspace_items": "invalid",
            "max_active_context_items": -2,
            "max_passive_context_items": "3",
            "max_archived_context_items": None,
            "max_total_context_items": 0,
        }
    )
    assert scope["max_workspace_items"] is None
    assert scope["max_active_context_items"] == 0
    assert scope["max_passive_context_items"] == 3
    assert scope["max_archived_context_items"] is None
    assert scope["max_total_context_items"] == 0
