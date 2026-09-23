from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.application.workflows.turn_artifact_destination import TurnArtifactDestination
from orket.application.workflows.turn_artifact_writer import TurnArtifactWriter
from orket.core.contracts.tool_invocation_contracts import (
    PROTOCOL_RECEIPT_SCHEMA_VERSION,
    build_tool_invocation_manifest,
    compute_tool_call_hash,
)


def _destination(writer: TurnArtifactWriter, turn_index: int) -> TurnArtifactDestination:
    return TurnArtifactDestination(
        writer=writer,
        workspace=writer.workspace.resolve(),
        session_id="s1",
        issue_id="ISSUE-1",
        role_name="coder",
        role_id="CODER",
        turn_index=turn_index,
    )


# Layer: integration
def test_turn_artifact_writer_replay_round_trip(tmp_path: Path) -> None:
    writer = TurnArtifactWriter(tmp_path)
    destination = _destination(writer, 1)
    payload = {"ok": True, "value": 7}
    args = {"path": "agent_output/main.py"}

    writer.persist_tool_result(
        destination=destination,
        tool_name="write_file",
        tool_args=args,
        result=payload,
    )

    loaded = writer.load_replay_tool_result(
        destination=destination,
        tool_name="write_file",
        tool_args=args,
        resume_mode=True,
    )

    assert loaded == payload


# Layer: integration
def test_turn_artifact_writer_checkpoint_writes_file(tmp_path: Path) -> None:
    writer = TurnArtifactWriter(tmp_path)
    writer.write_turn_checkpoint(
        destination=_destination(writer, 2),
        prompt_hash="abc123",
        selected_model="test-model",
        tool_calls=[],
        state_delta={"from": "doing", "to": "done"},
        captured_at="2026-09-23T12:34:56+00:00",
        prompt_metadata={"prompt_id": "p1"},
    )

    out_dir = tmp_path / "observability" / "s1" / "issue-1" / "002_coder"
    checkpoint = out_dir / "checkpoint.json"
    assert checkpoint.exists()
    data = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert data["prompt_hash"] == "abc123"
    assert data["captured_at"] == "2026-09-23T12:34:56+00:00"


# Layer: integration
def test_turn_artifact_writer_operation_result_round_trip(tmp_path: Path) -> None:
    writer = TurnArtifactWriter(tmp_path)
    destination = _destination(writer, 3)
    writer.persist_operation_result(
        destination=destination,
        operation_id="op-123",
        tool_name="write_file",
        tool_args={"path": "agent_output/main.py", "content": "ok"},
        result={"ok": True, "status": "done"},
    )

    loaded = writer.load_operation_result(
        destination=destination,
        operation_id="op-123",
    )
    assert loaded is not None
    assert loaded["operation_id"] == "op-123"
    assert loaded["result"] == {"ok": True, "status": "done"}


# Layer: integration
def test_turn_artifact_writer_append_protocol_receipt_writes_digest(tmp_path: Path) -> None:
    writer = TurnArtifactWriter(tmp_path)
    manifest = build_tool_invocation_manifest(
        run_id="s1",
        tool_name="write_file",
        control_plane_run_id="turn-tool-run:s1:ISSUE-1:coder:0004",
        control_plane_attempt_id="turn-tool-run:s1:ISSUE-1:coder:0004:attempt:0001",
        control_plane_step_id="op-1",
        control_plane_reservation_id="turn-tool-reservation:turn-tool-run:s1:ISSUE-1:coder:0004",
        control_plane_lease_id="turn-tool-lease:turn-tool-run:s1:ISSUE-1:coder:0004",
        control_plane_resource_id="namespace:issue:ISSUE-1",
    )
    tool_args = {"path": "agent_output/main.py"}
    tool_call_hash = compute_tool_call_hash(
        tool_name="write_file",
        tool_args=tool_args,
        tool_contract_version=str(manifest["tool_contract_version"]),
        capability_profile=str(manifest["capability_profile"]),
    )
    receipt = writer.append_protocol_receipt(
        destination=_destination(writer, 4),
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
    receipt_log = tmp_path / "observability" / "s1" / "issue-1" / "004_coder" / "protocol_receipts.log"
    assert receipt_log.exists()
    rows = [json.loads(line) for line in receipt_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows[0]["receipt_seq"] == 1
    assert rows[0]["schema_version"] == PROTOCOL_RECEIPT_SCHEMA_VERSION
    assert rows[0]["receipt_digest"] == receipt["receipt_digest"]
    manifest_payload = rows[0]["tool_invocation_manifest"]
    assert manifest_payload["tool_name"] == "write_file"
    assert manifest_payload["ring"] == "core"
    assert manifest_payload["schema_version"] == "1.0.0"
    assert manifest_payload["determinism_class"] == "workspace"
    assert manifest_payload["capability_profile"] == "workspace"
    assert manifest_payload["tool_contract_version"] == "1.0.0"
    assert manifest_payload["control_plane_run_id"] == "turn-tool-run:s1:ISSUE-1:coder:0004"
    assert (
        manifest_payload["control_plane_attempt_id"]
        == "turn-tool-run:s1:ISSUE-1:coder:0004:attempt:0001"
    )
    assert manifest_payload["control_plane_step_id"] == "op-1"
    assert (
        manifest_payload["control_plane_reservation_id"]
        == "turn-tool-reservation:turn-tool-run:s1:ISSUE-1:coder:0004"
    )
    assert manifest_payload["control_plane_lease_id"] == "turn-tool-lease:turn-tool-run:s1:ISSUE-1:coder:0004"
    assert manifest_payload["control_plane_resource_id"] == "namespace:issue:ISSUE-1"
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
        destination=_destination(writer, 4),
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

    compat_translation_path = tmp_path / "observability" / "s1" / "issue-1" / "004_coder" / "compat_translation.json"
    assert compat_translation_path.exists()
    payload = json.loads(compat_translation_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0"
    assert payload["translations"][0]["compat_tool_name"] == "openclaw.file_read"
    assert payload["translations"][0]["operation_id"] == "op-1"
    latency_profile_path = tmp_path / "observability" / "s1" / "issue-1" / "004_coder" / "compat_latency_profile.json"
    assert latency_profile_path.exists()
    latency_payload = json.loads(latency_profile_path.read_text(encoding="utf-8"))
    assert latency_payload["profiles"][0]["compat_tool"] == "openclaw.file_read"
    assert latency_payload["profiles"][0]["latency_ms"] == 12


# Layer: contract
def test_turn_artifact_writer_append_protocol_receipt_rejects_missing_manifest(tmp_path: Path) -> None:
    writer = TurnArtifactWriter(tmp_path)
    with pytest.raises(ValueError, match="E_TOOL_INVOCATION_MANIFEST_REQUIRED"):
        writer.append_protocol_receipt(
            destination=_destination(writer, 4),
            receipt={"run_id": "s1", "step_id": "ISSUE-1:4", "receipt_seq": 1, "tool": "write_file"},
        )


# Layer: contract
def test_turn_artifact_writer_rejects_foreign_destination(tmp_path: Path) -> None:
    writer = TurnArtifactWriter(tmp_path)
    foreign = TurnArtifactWriter(tmp_path)
    with pytest.raises(ValueError, match="E_TURN_ARTIFACT_WRITER_MISMATCH"):
        writer.write_turn_artifact(
            destination=_destination(foreign, 1), filename="result.json", content="{}",
        )


# Layer: contract
def test_turn_artifact_writer_uses_captured_workspace_after_writer_mutation(tmp_path: Path) -> None:
    writer = TurnArtifactWriter(tmp_path / "original")
    destination = _destination(writer, 1)
    writer.workspace = tmp_path / "changed"

    writer.write_turn_artifact(
        destination=destination, filename="result.json", content="{}",
    )

    assert destination.file_path("result.json").read_text(encoding="utf-8") == "{}"
    assert not (tmp_path / "changed" / "observability").exists()


@pytest.mark.parametrize(
    ("method", "token", "field"),
    [
        ("artifact", "../result.json", "filename"),
        ("tool", "../read", "tool_name"),
        ("operation", "../op", "operation_id"),
    ],
)
# Layer: contract
def test_turn_artifact_writer_rejects_path_bearing_tokens(
    tmp_path: Path, method: str, token: str, field: str,
) -> None:
    writer = TurnArtifactWriter(tmp_path)
    destination = _destination(writer, 1)
    with pytest.raises(ValueError, match=rf"E_TURN_ARTIFACT_PATH_COMPONENT:{field}"):
        if method == "artifact":
            writer.write_turn_artifact(
                destination=destination, filename=token, content="{}",
            )
        elif method == "tool":
            writer.tool_result_path(
                destination=destination, tool_name=token, tool_args={},
            )
        else:
            writer.operation_result_path(
                destination=destination, operation_id=token,
            )
    assert not destination.output_dir.exists()
