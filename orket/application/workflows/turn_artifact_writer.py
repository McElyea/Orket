from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from orket.core.domain.execution import ExecutionTurn
from orket.naming import sanitize_name
from orket.schema import IssueConfig, RoleConfig

from .protocol_hashing import ProtocolCanonicalizationError, hash_canonical_json, hash_framed_fields
from .tool_invocation_contracts import (
    PROTOCOL_RECEIPT_SCHEMA_VERSION,
    compute_tool_call_hash,
    normalize_tool_invocation_manifest,
)
from .turn_compatibility_artifacts import append_compatibility_artifacts


class TurnArtifactWriter:
    """Observability artifact and replay cache writer for turn execution."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    def message_hash(self, messages: list[dict[str, str]]) -> str:
        return hash_framed_fields("message_hash", [messages])[:16]

    def memory_trace_enabled(self, context: dict[str, Any]) -> bool:
        if bool(context.get("memory_trace_enabled", False)):
            return True
        return str(context.get("visibility_mode", "")).strip() != ""

    def hash_payload(self, payload: Any) -> str:
        try:
            return hash_canonical_json(payload)
        except ProtocolCanonicalizationError:
            fallback = {"non_canonical_repr": str(payload)}
            return hash_canonical_json(fallback)

    @staticmethod
    def _load_json_dict(path: Path) -> dict[str, Any] | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            return None
        return payload if isinstance(payload, dict) else None

    def append_memory_event(
        self,
        context: dict[str, Any],
        *,
        role_name: str,
        interceptor: str,
        decision_type: str,
        tool_calls: list[dict[str, Any]] | None = None,
        guardrails_triggered: list[str] | None = None,
        retrieval_event_ids: list[str] | None = None,
    ) -> None:
        events = context.get("_memory_trace_events")
        if not isinstance(events, list):
            return
        events.append(
            {
                "role": role_name,
                "interceptor": str(interceptor).strip(),
                "decision_type": str(decision_type).strip(),
                "tool_calls": list(tool_calls or []),
                "guardrails_triggered": list(guardrails_triggered or []),
                "retrieval_event_ids": list(retrieval_event_ids or []),
            }
        )

    def emit_memory_traces(
        self,
        *,
        session_id: str,
        issue_id: str,
        role_name: str,
        turn_index: int,
        issue: IssueConfig,
        role: RoleConfig,
        context: dict[str, Any],
        turn: ExecutionTurn | None = None,
        failure_reason: str = "",
        failure_type: str = "",
    ) -> None:
        if not self.memory_trace_enabled(context):
            return

        normalization_version = str(context.get("normalization_version") or "json-v1").strip() or "json-v1"
        tool_profile_version = str(context.get("tool_profile_version") or "unknown-v1").strip() or "unknown-v1"

        trace_tool_calls: list[dict[str, Any]] = []
        for call in (turn.tool_calls if turn is not None else []) or []:
            trace_tool_calls.append(
                {
                    "tool_name": str(call.tool or "").strip(),
                    "tool_profile_version": tool_profile_version,
                    "normalized_args": dict(call.args or {}),
                    "normalization_version": normalization_version,
                    "tool_result_fingerprint": self.hash_payload(call.result if isinstance(call.result, dict) else {}),
                    "side_effect_fingerprint": None,
                }
            )

        collected_events = (
            context.get("_memory_trace_events") if isinstance(context.get("_memory_trace_events"), list) else []
        )
        if collected_events:
            trace_events: list[dict[str, Any]] = []
            for idx, evt in enumerate(collected_events):
                trace_events.append(
                    {
                        "event_id": f"{session_id}:{issue_id}:{role_name}:{turn_index}:{idx}",
                        "index": idx,
                        "role": str(evt.get("role", role_name)),
                        "interceptor": str(evt.get("interceptor", "turn")),
                        "decision_type": str(evt.get("decision_type", "execute_turn")),
                        "tool_calls": list(evt.get("tool_calls") or []),
                        "guardrails_triggered": list(evt.get("guardrails_triggered") or []),
                        "retrieval_event_ids": list(evt.get("retrieval_event_ids") or []),
                    }
                )
        else:
            fallback_interceptor = "on_turn_failure" if failure_reason else "turn"
            fallback_decision = str(failure_type).strip() if failure_reason else "execute_turn"
            trace_events = [
                {
                    "event_id": f"{session_id}:{issue_id}:{role_name}:{turn_index}:0",
                    "index": 0,
                    "role": role_name,
                    "interceptor": fallback_interceptor,
                    "decision_type": fallback_decision or "execute_turn",
                    "tool_calls": trace_tool_calls,
                    "guardrails_triggered": list(context.get("guardrails_triggered") or []),
                    "retrieval_event_ids": [
                        str((row or {}).get("retrieval_event_id", "")).strip()
                        for row in (context.get("memory_retrieval_trace_events") or [])
                        if str((row or {}).get("retrieval_event_id", "")).strip()
                    ],
                }
            ]

        output_type = str(context.get("output_type") or "").strip()
        if not output_type:
            output_type = "error" if failure_reason else "text"
        output_struct: dict[str, Any] = {"type": output_type}
        if failure_reason:
            output_struct["status"] = "failed"
            output_struct["failure_type"] = str(failure_type).strip() or "turn_failed"
        elif output_type == "text":
            output_struct["sections"] = ["body"]
        output_shape_hash = self.hash_payload(output_struct)

        memory_trace = {
            "run_id": session_id,
            "workflow_id": str(context.get("workflow_id") or "turn_executor").strip() or "turn_executor",
            "memory_snapshot_id": str(context.get("memory_snapshot_id") or "unknown").strip() or "unknown",
            "visibility_mode": str(context.get("visibility_mode") or "off").strip() or "off",
            "model_config_id": str(context.get("model_config_id") or context.get("selected_model") or "unknown").strip()
            or "unknown",
            "policy_set_id": str(context.get("policy_set_id") or "unknown").strip() or "unknown",
            "determinism_trace_schema_version": "memory.determinism_trace.v1",
            "events": trace_events,
            "output": {
                "output_type": output_type,
                "output_shape_hash": output_shape_hash,
                "normalization_version": normalization_version,
            },
            "issue_id": issue.id,
            "role_id": role.id,
            "metadata": {"truncated": False},
        }
        retrieval_trace = {
            "events": list(context.get("memory_retrieval_trace_events") or []),
            "retrieval_trace_schema_version": "memory.retrieval_trace.v1",
            "metadata": {"truncated": False},
        }
        self.write_turn_artifact(
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            filename="memory_trace.json",
            content=json.dumps(memory_trace, indent=2, ensure_ascii=False, default=str),
        )
        self.write_turn_artifact(
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            filename="memory_retrieval_trace.json",
            content=json.dumps(retrieval_trace, indent=2, ensure_ascii=False, default=str),
        )

    def write_turn_artifact(
        self,
        *,
        session_id: str,
        issue_id: str,
        role_name: str,
        turn_index: int,
        filename: str,
        content: str,
    ) -> None:
        out_dir = self._turn_output_dir(
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / filename).write_text(content, encoding="utf-8")

    def write_turn_checkpoint(
        self,
        *,
        session_id: str,
        issue_id: str,
        role_name: str,
        turn_index: int,
        prompt_hash: str,
        selected_model: Any,
        tool_calls: list[dict[str, Any]],
        state_delta: dict[str, Any],
        prompt_metadata: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "run_id": session_id,
            "issue_id": issue_id,
            "turn_index": turn_index,
            "role": role_name,
            "prompt_hash": prompt_hash,
            "model": selected_model,
            "tool_calls": tool_calls,
            "state_delta": state_delta,
            "prompt_metadata": prompt_metadata or {},
            "captured_at": datetime.now(UTC).isoformat(),
        }
        self.write_turn_artifact(
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            filename="checkpoint.json",
            content=json.dumps(payload, indent=2, ensure_ascii=False),
        )

    def tool_replay_key(self, tool_name: str, tool_args: dict[str, Any]) -> str:
        return hash_framed_fields("tool_replay_key", [tool_name, tool_args])[:12]

    def tool_result_path(
        self,
        *,
        session_id: str,
        issue_id: str,
        role_name: str,
        turn_index: int,
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> Path:
        replay_key = self.tool_replay_key(tool_name, tool_args)
        out_dir = self._turn_output_dir(
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir / f"tool_result_{sanitize_name(tool_name)}_{replay_key}.json"

    def load_replay_tool_result(
        self,
        *,
        session_id: str,
        issue_id: str,
        role_name: str,
        turn_index: int,
        tool_name: str,
        tool_args: dict[str, Any],
        resume_mode: bool,
    ) -> dict[str, Any] | None:
        if not resume_mode:
            return None
        path = self.tool_result_path(
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            tool_name=tool_name,
            tool_args=tool_args,
        )
        if not path.exists():
            return None
        return self._load_json_dict(path)

    def persist_tool_result(
        self,
        *,
        session_id: str,
        issue_id: str,
        role_name: str,
        turn_index: int,
        tool_name: str,
        tool_args: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        path = self.tool_result_path(
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            tool_name=tool_name,
            tool_args=tool_args,
        )
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    def operation_result_path(
        self,
        *,
        session_id: str,
        issue_id: str,
        role_name: str,
        turn_index: int,
        operation_id: str,
    ) -> Path:
        out_dir = self._turn_output_dir(
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
        )
        operation_dir = out_dir / "operations"
        operation_dir.mkdir(parents=True, exist_ok=True)
        op_id = sanitize_name(str(operation_id).strip() or "unknown-operation")
        return operation_dir / f"{op_id}.json"

    def load_operation_result(
        self,
        *,
        session_id: str,
        issue_id: str,
        role_name: str,
        turn_index: int,
        operation_id: str,
    ) -> dict[str, Any] | None:
        path = self.operation_result_path(
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            operation_id=operation_id,
        )
        if not path.exists():
            return None
        return self._load_json_dict(path)

    def persist_operation_result(
        self,
        *,
        session_id: str,
        issue_id: str,
        role_name: str,
        turn_index: int,
        operation_id: str,
        tool_name: str,
        tool_args: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        path = self.operation_result_path(
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            operation_id=operation_id,
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
        self,
        *,
        session_id: str,
        issue_id: str,
        role_name: str,
        turn_index: int,
        receipt: dict[str, Any],
    ) -> dict[str, Any]:
        base_receipt = dict(receipt or {})
        base_receipt["schema_version"] = str(base_receipt.get("schema_version") or PROTOCOL_RECEIPT_SCHEMA_VERSION)
        manifest = normalize_tool_invocation_manifest(
            manifest=base_receipt.get("tool_invocation_manifest")
            if isinstance(base_receipt.get("tool_invocation_manifest"), dict)
            else None,
            run_id=str(session_id),
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
                turn_output_dir=self._turn_output_dir(
                    session_id=session_id,
                    issue_id=issue_id,
                    role_name=role_name,
                    turn_index=turn_index,
                ),
                operation_id=str(base_receipt.get("operation_id") or ""),
                translation=compat_translation,
            )
        receipt_digest = hash_canonical_json(base_receipt)
        base_receipt["receipt_digest"] = receipt_digest
        line = json.dumps(base_receipt, ensure_ascii=False, separators=(",", ":"))
        receipt_path = (
            self._turn_output_dir(
                session_id=session_id,
                issue_id=issue_id,
                role_name=role_name,
                turn_index=turn_index,
            )
            / "protocol_receipts.log"
        )
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        with receipt_path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")
        return base_receipt

    def _turn_output_dir(
        self,
        *,
        session_id: str,
        issue_id: str,
        role_name: str,
        turn_index: int,
    ) -> Path:
        return (
            self.workspace
            / "observability"
            / sanitize_name(session_id)
            / sanitize_name(issue_id)
            / f"{turn_index:03d}_{sanitize_name(role_name)}"
        )
