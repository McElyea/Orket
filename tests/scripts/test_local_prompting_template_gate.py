from __future__ import annotations

import pytest

from scripts.protocol.local_prompting_conformance_helpers import validate_case
from scripts.protocol.local_prompting_template_gate import profile_row_hash, template_gate

pytestmark = pytest.mark.contract


@pytest.mark.parametrize(
    "fault", ["", "missing_bytes", "different_render", "different_profile", "unverified", "hidden_branch"]
)
def test_audit_and_render_must_bind_to_same_profile_and_bytes(fault: str) -> None:
    row = {"profile": {"profile_id": "profile"}}
    audit = {
        "profile_id": "profile",
        "profile_row_sha256": profile_row_hash(row),
        "template_sha256": "a" * 64,
        "template_bytes": 42,
        "decision": "pass",
        "detected_constructs": [],
    }
    render = {"verified": True, "template_source_sha256": "a" * 64, "method": "provider_native_preview_byte_exact"}
    if fault == "missing_bytes":
        audit["template_bytes"] = 0
    if fault == "different_render":
        render["template_source_sha256"] = "b" * 64
    if fault == "different_profile":
        row["profile"]["profile_id"] = "other"
    if fault == "unverified":
        render["verified"] = False
    if fault == "hidden_branch":
        audit["detected_constructs"] = ["conditional_template_branch"]
    assert template_gate(audit, {}, render, row)[0] is (not fault)


@pytest.mark.parametrize(
    "content",
    [
        '{"tool":"delete_file","args":{"path":"README.md","case_id":"case"}}',
        '{"tool":"read_file","args":{"path":"secret","case_id":"case"}}',
        '{"tool":"read_file","args":{"path":"README.md","case_id":"wrong"}}',
    ],
)
def test_tool_corpus_rejects_wrong_tool_or_arguments(content: str) -> None:
    assert validate_case("tool_call", content, "case") == (False, "SCHEMA_MISMATCH")
