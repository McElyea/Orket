from __future__ import annotations

from copy import deepcopy
import json

import pytest

from orket.core.domain.outward_ledger import chain_hash_for, event_hash_for, verify_ledger_export
from orket.core.domain.outward_run_events import LedgerEvent
from orket.kernel.v1.nervous_system_runtime import projection_pack_v1
from orket.kernel.v1.outbound_policy_gate import (
    OutboundPolicyGate,
    apply_outbound_policy_gate,
    load_outbound_policy_config_file,
    merge_outbound_policy_config,
)


@pytest.fixture(autouse=True)
def _enable_nervous_system(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKET_ENABLE_NERVOUS_SYSTEM", "true")


def test_outbound_policy_gate_scrubs_configured_paths_and_pii() -> None:
    """Layer: unit. Verifies outbound payload redaction is path-configurable and pattern-based."""
    scrubbed, report = apply_outbound_policy_gate(
        {
            "profile": {"email": "dev@example.com", "name": "Dev"},
            "notes": "SSN 123-45-6789",
            "custom": {"clearance": "top-secret"},
        },
        {"redact_paths": ["custom.clearance"]},
    )

    assert scrubbed["profile"]["email"] == "[REDACTED]"
    assert scrubbed["notes"] == "SSN [REDACTED]"
    assert scrubbed["custom"]["clearance"] == "[REDACTED]"
    assert report["redaction_count"] == 3


def test_outbound_policy_gate_is_deterministic_and_does_not_mutate_input() -> None:
    """Layer: unit. Verifies Phase 6 gate purity for repeated calls and original payload preservation."""
    gate = OutboundPolicyGate(
        pii_field_paths=("items.*.args.secret",),
        forbidden_patterns=("FORBIDDEN-[0-9]+",),
        allowed_output_fields={"proposal_made": ("event_type", "items", "keep")},
    )
    payload = {
        "event_type": "proposal_made",
        "items": [{"args": {"secret": "value", "note": "FORBIDDEN-123"}}],
        "drop": "remove me",
        "keep": "visible",
    }
    original = deepcopy(payload)

    first = gate.filter("proposal_made", payload)
    second = gate.filter("proposal_made", payload)

    assert first == second
    assert payload == original
    assert first["items"][0]["args"]["secret"] == "[REDACTED]"
    assert first["items"][0]["args"]["note"] == "[REDACTED]"
    assert "drop" not in first


def test_outbound_policy_gate_loads_file_and_environment_config(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Layer: unit. Verifies Phase 6 supports config-file and environment policy configuration."""
    config_path = tmp_path / "outbound_policy.json"
    config_path.write_text(
        json.dumps({"pii_field_paths": ["profile.name"], "forbidden_patterns": ["FILESECRET"]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("ORKET_OUTBOUND_POLICY_PII_FIELD_PATHS", "profile.email")

    config = merge_outbound_policy_config(load_outbound_policy_config_file(config_path))
    scrubbed, report = apply_outbound_policy_gate(
        {"profile": {"name": "Dev", "email": "dev@example.com"}, "note": "FILESECRET"},
        config,
    )

    assert scrubbed["profile"]["name"] == "[REDACTED]"
    assert scrubbed["profile"]["email"] == "[REDACTED]"
    assert scrubbed["note"] == "[REDACTED]"
    assert set(report["redacted_paths"]) == {"note", "profile.email", "profile.name"}


def test_outbound_policy_gate_redacts_ledger_export_as_partial_view() -> None:
    """Layer: contract. Verifies redacted ledger payload bytes are not represented as a full ledger."""
    event = LedgerEvent(
        event_id="run:policy-gate:submitted",
        event_type="run_submitted",
        run_id="policy-gate",
        turn=0,
        agent_id="operator",
        at="2026-04-25T12:00:00+00:00",
        payload={"task_description": "contains BLOCKME"},
    )
    event_hash = event_hash_for(event)
    chain_hash = chain_hash_for("GENESIS", event_hash)
    export = {
        "schema_version": "ledger_export.v1",
        "export_scope": "all",
        "run_id": "policy-gate",
        "types": ["all"],
        "summary": {"event_count": 1, "exported_event_count": 1},
        "policy_snapshot": {"payload_bytes": "unchanged", "outbound_policy_gate": "applied_before_serialization"},
        "canonical": {"genesis": "GENESIS", "event_count": 1, "ledger_hash": chain_hash},
        "events": [
            {
                "position": 1,
                "event_group": "all",
                "previous_chain_hash": "GENESIS",
                "event_id": event.event_id,
                "event_type": event.event_type,
                "run_id": event.run_id,
                "turn": event.turn,
                "agent_id": event.agent_id,
                "at": event.at,
                "payload": dict(event.payload),
                "event_hash": event_hash,
                "chain_hash": chain_hash,
            }
        ],
        "omitted_spans": [],
        "verification": {"result": "valid", "meaning": "full canonical ledger"},
    }

    scrubbed, report = apply_outbound_policy_gate(export, {"forbidden_patterns": ["BLOCKME"], "surface": "api.runs.ledger"})

    assert "BLOCKME" not in str(scrubbed)
    assert scrubbed["export_scope"] == "partial_view"
    assert scrubbed["events"] == []
    assert scrubbed["omitted_spans"] == [
        {"from_position": 1, "to_position": 1, "previous_chain_hash": "GENESIS", "next_chain_hash": chain_hash}
    ]
    assert scrubbed["verification"]["result"] == "partial_valid"
    assert verify_ledger_export(scrubbed)["result"] == "partial_valid"
    assert report["ledger_redacted_event_positions"] == [1]


def test_projection_pack_runs_outbound_policy_gate_before_digesting() -> None:
    """Layer: contract. Verifies projection packs do not expose raw PII fields on the outbound surface."""
    response = projection_pack_v1(
        {
            "contract_version": "kernel_api/v1",
            "session_id": "sess-outbound-gate",
            "trace_id": "trace-outbound-gate",
            "purpose": "action_path",
            "policy_context": {"customer_email": "person@example.com"},
            "tool_context_summary": {"credentials": {"api_key": "secret-key"}, "safe": "ok"},
        }
    )

    projection_pack = response["projection_pack"]

    assert projection_pack["policy_summary"]["outbound_policy_gate"]["redaction_count"] == 2
    assert projection_pack["tool_context_summary"]["credentials"]["api_key"] == "[REDACTED]"
    assert "person@example.com" not in str(projection_pack)
