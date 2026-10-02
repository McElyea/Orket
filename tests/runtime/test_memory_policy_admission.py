"""Contract decisions with explicit observation time; no memory-store effects claimed."""
from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from orket.runtime.policy.truthful_memory_policy import (
    classify_memory_trust_level,
    evaluate_memory_write_policy,
    render_reference_context_rows,
    render_scoped_memory_rows,
)

pytestmark = pytest.mark.contract
NOW = datetime(2026, 9, 21, tzinfo=UTC)


@pytest.mark.parametrize("metadata,expected", [
    ({"observed_at": "2026-09-20", "max_age_minutes": "30"}, "stale_risk"),
    ({"observed_at": "2026-09-20", "max_age_minutes": "invalid"}, "authoritative"),
    ({"observed_at": "2026-09-20", "max_age_minutes": " "}, "authoritative"),
    ({"refreshed_at": "2026-09-20", "max_age_minutes": 1}, "authoritative"),
    ({"trust_level": "stale_risk"}, "stale_risk"),
    ({"observed_at": "invalid"}, "authoritative"),
])
def test_staleness_and_refresh_precedence_preserve_metadata(metadata, expected):
    before = deepcopy(metadata)
    assert classify_memory_trust_level(scope="profile_memory", observed_at=NOW, metadata=metadata) == expected
    assert metadata == before


@pytest.mark.parametrize("scope,metadata,expected", [
    ("session_memory", {"kind": "chat_input"}, "authoritative"),
    ("session_memory", {}, "advisory"),
    ("project_memory", {}, "unverified"),
    ("project_memory", {"type": "decision"}, "advisory"),
    ("project_memory", {"memory_class": "unknown"}, "unverified"),
])
def test_default_trust_does_not_promote_unknown_memory(scope, metadata, expected):
    assert classify_memory_trust_level(scope=scope, observed_at=NOW, metadata=metadata) == expected


def test_unchanged_fact_needs_no_correction_and_reference_trust_has_safe_default():
    metadata = {"write_rationale": "retained user rationale"}
    same = evaluate_memory_write_policy(scope="profile_memory", key="user_fact.name", value="Aster",
                                        existing_value="Aster", metadata=metadata)
    assert same.allow_write and same.conflict_resolution == "no_change"
    assert same.metadata["write_rationale"] == "retained user rationale" and metadata == {
        "write_rationale": "retained user rationale",
    }
    reference = evaluate_memory_write_policy(scope="project_memory", key="context", value="note",
                                             metadata={"trust_level": "invented"})
    assert reference.allow_write and reference.metadata["trust_level"] == "advisory"


def test_renderers_omit_empty_and_unverified_rows_without_changing_them():
    rows = [{"content": " "}, {"content": "unverified"},
            {"content": "advice", "metadata": {"trust_level": "advisory"}}]
    before = deepcopy(rows)
    assert render_reference_context_rows(rows, observed_at=NOW) == "- [reference_context][trust=advisory] advice"
    assert rows == before
    scoped = [SimpleNamespace(key="", value=""),
              SimpleNamespace(key="name", value="Aster", scope="profile_memory", metadata={}),
              SimpleNamespace(key="old", value="discard", scope="profile_memory",
                              metadata={"trust_level": "stale_risk"})]
    assert render_scoped_memory_rows(scoped, prefix="profile", observed_at=NOW) == [
        "- [profile][trust=authoritative] name: Aster",
    ]
