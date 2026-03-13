from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.application.workflows.turn_artifact_writer import TurnArtifactWriter
from orket.application.workflows.tool_invocation_contracts import (
    build_tool_invocation_manifest,
    compute_tool_call_hash,
)


def test_turn_artifact_writer_replay_round_trip(tmp_path: Path) -> None:
    writer = TurnArtifactWriter(tmp_path)
    payload = {"ok": True, "value": 7}
    args = {"path": "agent_output/main.py"}

    writer.persist_tool_result(
        session_id="s1",
        issue_id="ISSUE-1",
        role_name="coder",
        turn_index=1,
        tool_name="write_file",
        tool_args=args,
        result=payload,
    )

    loaded = writer.load_replay_tool_result(
        session_id="s1",
        issue_id="ISSUE-1",
        role_name="coder",
        turn_index=1,
        tool_name="write_file",
        tool_args=args,
        resume_mode=True,
    )

    assert loaded == payload


def test_turn_artifact_writer_checkpoint_writes_file(tmp_path: Path) -> None:
    writer = TurnArtifactWriter(tmp_path)
    writer.write_turn_checkpoint(
        session_id="s1",
        issue_id="ISSUE-1",
        role_name="coder",
        turn_index=2,
        prompt_hash="abc123",
        selected_model="test-model",
        tool_calls=[],
        state_delta={"from": "doing", "to": "done"},
        prompt_metadata={"prompt_id": "p1"},
    )

    out_dir = tmp_path / "observability" / "s1" / "ISSUE-1" / "002_coder"
    checkpoint = out_dir / "checkpoint.json"
    assert checkpoint.exists()
    data = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert data["prompt_hash"] == "abc123"


def test_turn_artifact_writer_operation_result_round_trip(tmp_path: Path) -> None:
    writer = TurnArtifactWriter(tmp_path)
    writer.persist_operation_result(
        session_id="s1",
        issue_id="ISSUE-1",
        role_name="coder",
        turn_index=3,
        operation_id="op-123",
        tool_name="write_file",
        tool_args={"path": "agent_output/main.py", "content": "ok"},
        result={"ok": True, "status": "done"},
    )

    loaded = writer.load_operation_result(
        session_id="s1",
        issue_id="ISSUE-1",
        role_name="coder",
        turn_index=3,
        operation_id="op-123",
    )
    assert loaded is not None
    assert loaded["operation_id"] == "op-123"
    assert loaded["result"] == {"ok": True, "status": "done"}


# Layer: integration
def test_turn_artifact_writer_append_protocol_receipt_writes_digest(tmp_path: Path) -> None:
    writer = TurnArtifactWriter(tmp_path)
    manifest = build_tool_invocation_manifest(run_id="s1", tool_name="write_file")
    tool_args = {"path": "agent_output/main.py"}
    tool_call_hash = compute_tool_call_hash(
        tool_name="write_file",
        tool_args=tool_args,
        tool_contract_version=str(manifest["tool_contract_version"]),
        capability_profile=str(manifest["capability_profile"]),
    )
    receipt = writer.append_protocol_receipt(
        session_id="s1",
        issue_id="ISSUE-1",
        role_name="coder",
        turn_index=4,
        receipt={
            "run_id": "s1",
            "step_id": "ISSUE-1:4",
            "receipt_seq": 1,
            "tool": "write_file",
            "tool_args": tool_args,
            "tool_invocation_manifest": manifest,
            "tool_call_hash": tool_call_hash,
        },
    )
    assert isinstance(receipt.get("receipt_digest"), str)
    assert len(receipt["receipt_digest"]) == 64
    receipt_log = tmp_path / "observability" / "s1" / "ISSUE-1" / "004_coder" / "protocol_receipts.log"
    assert receipt_log.exists()
    rows = [json.loads(line) for line in receipt_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows[0]["receipt_seq"] == 1
    assert rows[0]["receipt_digest"] == receipt["receipt_digest"]
    manifest_payload = rows[0]["tool_invocation_manifest"]
    assert manifest_payload["tool_name"] == "write_file"
    assert manifest_payload["ring"] == "core"
    assert manifest_payload["schema_version"] == "1.0.0"
    assert manifest_payload["determinism_class"] == "workspace"
    assert manifest_payload["capability_profile"] == "workspace"
    assert manifest_payload["tool_contract_version"] == "1.0.0"
    assert "input_schema" not in manifest_payload
    assert "output_schema" not in manifest_payload
    assert "error_schema" not in manifest_payload
    assert "side_effect_class" not in manifest_payload
    assert "timeout" not in manifest_payload
    assert "retry_policy" not in manifest_payload


# Layer: integration
def test_turn_artifact_writer_append_protocol_receipt_writes_compat_translation_artifact(tmp_path: Path) -> None:
    writer = TurnArtifactWriter(tmp_path)
    manifest = build_tool_invocation_manifest(run_id="s1", tool_name="openclaw.file_read", ring="compatibility")
    tool_args = {"path": "agent_output/main.py"}
    tool_call_hash = compute_tool_call_hash(
        tool_name="openclaw.file_read",
        tool_args=tool_args,
        tool_contract_version=str(manifest["tool_contract_version"]),
        capability_profile=str(manifest["capability_profile"]),
    )
    writer.append_protocol_receipt(
        session_id="s1",
        issue_id="ISSUE-1",
        role_name="coder",
        turn_index=4,
        receipt={
            "run_id": "s1",
            "step_id": "ISSUE-1:4",
            "receipt_seq": 1,
            "operation_id": "op-1",
            "tool": "openclaw.file_read",
            "tool_args": tool_args,
            "tool_invocation_manifest": manifest,
            "tool_call_hash": tool_call_hash,
            "compat_translation": {
                "compat_tool_name": "openclaw.file_read",
                "mapping_version": 1,
                "mapping_determinism": "workspace",
                "schema_compatibility_range": ">=1.0.0 <2.0.0",
                "mapped_core_tools": ["workspace.read"],
                "translation_hash": "a" * 64,
                "latency_ms": 12,
            },
        },
    )

    compat_translation_path = tmp_path / "observability" / "s1" / "ISSUE-1" / "004_coder" / "compat_translation.json"
    assert compat_translation_path.exists()
    payload = json.loads(compat_translation_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0"
    assert payload["translations"][0]["compat_tool_name"] == "openclaw.file_read"
    assert payload["translations"][0]["operation_id"] == "op-1"
    latency_profile_path = tmp_path / "observability" / "s1" / "ISSUE-1" / "004_coder" / "compat_latency_profile.json"
    assert latency_profile_path.exists()
    latency_payload = json.loads(latency_profile_path.read_text(encoding="utf-8"))
    assert latency_payload["profiles"][0]["compat_tool"] == "openclaw.file_read"
    assert latency_payload["profiles"][0]["latency_ms"] == 12


# Layer: contract
def test_turn_artifact_writer_append_protocol_receipt_rejects_missing_manifest(tmp_path: Path) -> None:
    writer = TurnArtifactWriter(tmp_path)
    with pytest.raises(ValueError, match="E_TOOL_INVOCATION_MANIFEST_REQUIRED"):
        writer.append_protocol_receipt(
            session_id="s1",
            issue_id="ISSUE-1",
            role_name="coder",
            turn_index=4,
            receipt={"run_id": "s1", "step_id": "ISSUE-1:4", "receipt_seq": 1, "tool": "write_file"},
        )
