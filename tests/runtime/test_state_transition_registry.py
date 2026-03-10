from __future__ import annotations

import pytest

from orket.runtime.state_transition_registry import (
    state_transition_registry_snapshot,
    validate_state_token,
    validate_state_transition,
)


# Layer: unit
def test_state_transition_registry_snapshot_contains_required_domains() -> None:
    payload = state_transition_registry_snapshot()
    assert payload["schema_version"] == "1.0"
    domains = {row["domain"] for row in payload["domains"]}
    assert domains == {"session", "run", "tool_invocation", "voice", "ui"}


# Layer: contract
def test_validate_state_token_accepts_registered_state() -> None:
    assert validate_state_token(domain="session", state="TERMINAL_FAILURE") == "terminal_failure"


# Layer: contract
def test_validate_state_token_rejects_unknown_domain() -> None:
    with pytest.raises(ValueError, match="E_STATE_DOMAIN_UNKNOWN:unknown"):
        _ = validate_state_token(domain="unknown", state="running")


# Layer: contract
def test_validate_state_transition_accepts_registered_transition() -> None:
    assert validate_state_transition(domain="session", from_state="running", to_state="done") == ("running", "done")


# Layer: contract
def test_validate_state_transition_rejects_disallowed_transition() -> None:
    with pytest.raises(ValueError, match="E_STATE_TRANSITION_INVALID:session:done->failed"):
        _ = validate_state_transition(domain="session", from_state="done", to_state="failed")
