from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from orket.core.contracts.protocol_hashing import (
    ProtocolCanonicalizationError,
    hash_canonical_json,
    hash_framed_fields,
)
from orket.core.contracts.tool_invocation_contracts import (
    PROTOCOL_RECEIPT_SCHEMA_VERSION,
    compute_tool_call_hash,
    normalize_tool_invocation_manifest,
)

from .turn_artifact_destination import TurnArtifactDestination, artifact_component
from .turn_compatibility_artifacts import append_compatibility_artifacts

if TYPE_CHECKING:
    from .turn_memory_trace_artifacts import MemoryTracePublication


class TurnArtifactWriter:
    """Observability artifact and replay cache writer for turn execution."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    def message_hash(self, messages: list[dict[str, str]]) -> str:
        return hash_framed_fields("message_hash", [messages])[:16]

    def hash_payload(self, payload: Any) -> str:
        try:
            return hash_canonical_json(payload)
        except ProtocolCanonicalizationError:
            return hash_canonical_json({"non_canonical_repr": str(payload)})

    @staticmethod
    def _load_json_dict(path: Path) -> dict[str, Any] | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            return None
        return payload if isinstance(payload, dict) else None

    def write_turn_artifact(
        self, *, destination: TurnArtifactDestination, filename: str, content: str,
    ) -> None:
        destination.require_writer(self)
        path = destination.file_path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def write_memory_trace_publication(
        self, *, destination: TurnArtifactDestination, publication: MemoryTracePublication,
    ) -> None:
        destination.require_writer(self)
        self.write_turn_artifact(
            destination=destination,
            filename="memory_trace.json",
            content=publication.memory_trace,
        )
        self.write_turn_artifact(
            destination=destination,
            filename="memory_retrieval_trace.json",
            content=publication.retrieval_trace,
        )

    def write_turn_checkpoint(
        self,
        *,
        destination: TurnArtifactDestination,
        prompt_hash: str,
        selected_model: Any,
        tool_calls: list[dict[str, Any]],
        state_delta: dict[str, Any],
        captured_at: str,
        prompt_metadata: dict[str, Any] | None = None,
    ) -> None:
        destination.require_writer(self)
        payload = {
            "run_id": destination.session_id,
            "issue_id": destination.issue_id,
            "turn_index": destination.turn_index,
            "role": destination.role_name,
            "prompt_hash": prompt_hash,
            "model": selected_model,
            "tool_calls": tool_calls,
            "state_delta": state_delta,
            "prompt_metadata": prompt_metadata or {},
            "captured_at": captured_at,
        }
        self.write_turn_artifact(
            destination=destination,
            filename="checkpoint.json",
            content=json.dumps(payload, indent=2, ensure_ascii=False),
        )

    def tool_replay_key(self, tool_name: str, tool_args: dict[str, Any]) -> str:
        return hash_framed_fields("tool_replay_key", [tool_name, tool_args])[:12]

    def tool_result_path(
        self,
        *,
        destination: TurnArtifactDestination,
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> Path:
        destination.require_writer(self)
        replay_key = self.tool_replay_key(tool_name, tool_args)
        token = artifact_component(tool_name, field="tool_name")
        destination.output_dir.mkdir(parents=True, exist_ok=True)
        return destination.file_path(f"tool_result_{token}_{replay_key}.json")

    def load_replay_tool_result(
        self,
        *,
        destination: TurnArtifactDestination,
        tool_name: str,
        tool_args: dict[str, Any],
        resume_mode: bool,
    ) -> dict[str, Any] | None:
        destination.require_writer(self)
        if not resume_mode:
            return None
        path = self.tool_result_path(
            destination=destination, tool_name=tool_name, tool_args=tool_args,
        )
        if not path.exists():
            return None
        return self._load_json_dict(path)

    def persist_tool_result(
        self,
        *,
        destination: TurnArtifactDestination,
        tool_name: str,
        tool_args: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        destination.require_writer(self)
        path = self.tool_result_path(
            destination=destination, tool_name=tool_name, tool_args=tool_args,
        )
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    def operation_result_path(
        self, *, destination: TurnArtifactDestination, operation_id: str,
    ) -> Path:
        destination.require_writer(self)
        token = artifact_component(
            str(operation_id).strip() or "unknown-operation", field="operation_id",
        )
        operation_dir = destination.output_dir / "operations"
        operation_dir.mkdir(parents=True, exist_ok=True)
        return operation_dir / f"{token}.json"

    def load_operation_result(
        self, *, destination: TurnArtifactDestination, operation_id: str,
    ) -> dict[str, Any] | None:
        destination.require_writer(self)
        path = self.operation_result_path(
            destination=destination, operation_id=operation_id,
        )
        if not path.exists():
            return None
        return self._load_json_dict(path)

    def persist_operation_result(
        self,
        *,
        destination: TurnArtifactDestination,
        operation_id: str,
        tool_name: str,
        tool_args: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        destination.require_writer(self)
        path = self.operation_result_path(
            destination=destination, operation_id=operation_id,
        )
        payload = {
            "operation_id": operation_id,
            "tool": tool_name,
            "args": dict(tool_args or {}),
            "result": dict(result or {}),
            "result_digest": self.hash_payload(result if isinstance(result, dict) else {}),
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def append_protocol_receipt(
        self, *, destination: TurnArtifactDestination, receipt: dict[str, Any],
    ) -> dict[str, Any]:
        destination.require_writer(self)
        base_receipt = dict(receipt or {})
        base_receipt["schema_version"] = str(
            base_receipt.get("schema_version") or PROTOCOL_RECEIPT_SCHEMA_VERSION
        )
        manifest = normalize_tool_invocation_manifest(
            manifest=base_receipt.get("tool_invocation_manifest")
            if isinstance(base_receipt.get("tool_invocation_manifest"), dict)
            else None,
            run_id=destination.session_id,
            tool_name_fallback=str(base_receipt.get("tool") or ""),
        )
        if manifest is None:
            raise ValueError("E_TOOL_INVOCATION_MANIFEST_REQUIRED")
        base_receipt["tool_invocation_manifest"] = manifest
        observed_tool_call_hash = str(base_receipt.get("tool_call_hash") or "").strip()
        if not observed_tool_call_hash:
            raise ValueError("E_TOOL_CALL_HASH_REQUIRED")
        expected_tool_call_hash = compute_tool_call_hash(
            tool_name=str(manifest.get("tool_name") or ""),
            tool_args=dict(base_receipt.get("tool_args") or {})
            if isinstance(base_receipt.get("tool_args"), dict)
            else {},
            tool_contract_version=str(manifest.get("tool_contract_version") or ""),
            capability_profile=str(manifest.get("capability_profile") or ""),
        )
        if observed_tool_call_hash != expected_tool_call_hash:
            raise ValueError("E_TOOL_CALL_HASH_MISMATCH")
        compat_translation = base_receipt.get("compat_translation")
        if isinstance(compat_translation, dict):
            append_compatibility_artifacts(
                turn_output_dir=destination.output_dir,
                operation_id=str(base_receipt.get("operation_id") or ""),
                translation=compat_translation,
            )
        base_receipt["receipt_digest"] = hash_canonical_json(base_receipt)
        line = json.dumps(base_receipt, ensure_ascii=False, separators=(",", ":"))
        receipt_path = destination.file_path("protocol_receipts.log")
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        with receipt_path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")
        return base_receipt
