from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.async_file_tools import capture_file_roots
from orket.core.contracts import protocol_hashing
from orket.utils import sanitize_name


class ExecutionPipelineArtifactProvenanceMixin:
    if TYPE_CHECKING:
        workspace: Path

    async def _resolve_artifact_provenance_entries(
        self, *, run_id: str, workspace: Path,
    ) -> list[dict[str, Any]]:
        workspace, = capture_file_roots([workspace])
        captured_run_id = str(run_id)
        receipt_entries = await self._resolve_artifact_provenance_entries_from_receipts(
            run_id=captured_run_id, workspace=workspace)
        artifacts_by_path: dict[str, dict[str, Any]] = {
            str(entry["artifact_path"]): dict(entry) for entry in receipt_entries
        }
        log_entries = await self._resolve_artifact_provenance_entries_from_logs(
            run_id=captured_run_id,
            existing_paths=set(artifacts_by_path),
            workspace=workspace,
        )
        for entry in log_entries:
            artifacts_by_path[str(entry["artifact_path"])] = dict(entry)
        return [artifacts_by_path[key] for key in sorted(artifacts_by_path)]

    async def _resolve_artifact_provenance_entries_from_receipts(
        self, *, run_id: str, workspace: Path,
    ) -> list[dict[str, Any]]:
        captured_workspace, = capture_file_roots([workspace])
        captured_run_id = str(run_id)
        receipt_paths = await run_owned_thread(
            partial(self._artifact_provenance_receipt_paths, captured_run_id, captured_workspace),
            label="artifact-provenance-receipt-discovery",
        )
        artifacts_by_path: dict[str, dict[str, Any]] = {}
        for receipt_path in receipt_paths:
            issue_id, role_name, turn_index = self._artifact_provenance_receipt_context(
                receipt_path=receipt_path,
                run_id=captured_run_id,
                workspace=captured_workspace,
            )
            lines = await run_owned_thread(
                partial(_read_optional_lines, receipt_path), label="artifact-provenance-receipt-read",
            )
            if lines is None:
                continue
            for line in lines:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except (ValueError, TypeError):
                    continue
                if not isinstance(payload, dict):
                    continue
                entry = await self._artifact_provenance_entry_from_receipt(
                    receipt=payload, issue_id=issue_id, role_name=role_name,
                    turn_index=turn_index, workspace=captured_workspace,
                )
                if entry is not None:
                    artifacts_by_path[str(entry["artifact_path"])] = entry
        return [artifacts_by_path[key] for key in sorted(artifacts_by_path)]

    async def _resolve_artifact_provenance_entries_from_logs(
        self,
        *,
        run_id: str,
        existing_paths: set[str],
        workspace: Path,
    ) -> list[dict[str, Any]]:
        captured_workspace, = capture_file_roots([workspace])
        captured_run_id, captured_paths = str(run_id), set(existing_paths)
        log_path = captured_workspace / "orket.log"
        lines = await run_owned_thread(
            partial(_read_optional_lines, log_path), label="artifact-provenance-log-read",
        )
        if lines is None:
            return []
        starts_by_operation: dict[str, dict[str, Any]] = {}
        artifacts_by_path: dict[str, dict[str, Any]] = {}
        for line in lines:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except (ValueError, TypeError):
                continue
            if not isinstance(payload, dict):
                continue
            event_name = str(payload.get("event") or "").strip()
            if event_name not in {"tool_call_start", "tool_call_result"}:
                continue
            raw_data = payload.get("data")
            data: dict[str, Any] = dict(raw_data) if isinstance(raw_data, dict) else {}
            if str(data.get("session_id") or "").strip() != captured_run_id:
                continue
            operation_id = str(data.get("operation_id") or "").strip()
            if not operation_id:
                continue
            if event_name == "tool_call_start":
                if str(data.get("tool") or "").strip() != "write_file":
                    continue
                starts_by_operation[operation_id] = {
                    "issue_id": str(data.get("issue_id") or "").strip(),
                    "role_name": str(data.get("role") or payload.get("role") or "").strip(),
                    "turn_index": int(data.get("turn_index") or 0),
                    "tool_args": dict(data.get("args") or {}) if isinstance(data.get("args"), dict) else {},
                }
                continue
            if not bool(data.get("ok")):
                continue
            start = starts_by_operation.get(operation_id)
            if start is None:
                continue
            entry = await self._artifact_provenance_entry_from_log_pair(
                run_id=captured_run_id, operation_id=operation_id, start=start, workspace=captured_workspace,
            )
            if entry is None:
                continue
            artifact_path = str(entry.get("artifact_path") or "")
            if artifact_path in captured_paths:
                continue
            artifacts_by_path[artifact_path] = entry
        return [artifacts_by_path[key] for key in sorted(artifacts_by_path)]

    async def _artifact_provenance_entry_from_receipt(
        self,
        *,
        receipt: dict[str, Any],
        issue_id: str,
        role_name: str,
        turn_index: int,
        workspace: Path,
    ) -> dict[str, Any] | None:
        captured_receipt = deepcopy(receipt)
        captured_workspace, = capture_file_roots([workspace])
        captured_issue_id = str(issue_id or "").strip()
        captured_role_name = str(role_name or "").strip()
        captured_turn_index = int(turn_index)
        if str(captured_receipt.get("tool") or "").strip() != "write_file":
            return None
        execution_result = captured_receipt.get("execution_result")
        if not isinstance(execution_result, dict) or not bool(execution_result.get("ok")):
            return None
        artifact_location = await run_owned_thread(
            partial(self._resolve_workspace_artifact_location, execution_result, captured_receipt,
                    workspace=captured_workspace),
            label="artifact-provenance-location",
        )
        if artifact_location is None:
            return None
        artifact_path, resolved_artifact_path = artifact_location
        source_hash = str(
            captured_receipt.get("receipt_digest") or captured_receipt.get("tool_call_hash") or ""
        ).strip()
        if not source_hash:
            return None
        produced_at = await run_owned_thread(
            partial(self._artifact_produced_at, resolved_artifact_path), label="artifact-provenance-stat",
        )
        if not produced_at:
            return None
        manifest = (
            dict(captured_receipt.get("tool_invocation_manifest") or {})
            if isinstance(captured_receipt.get("tool_invocation_manifest"), dict)
            else {}
        )
        entry: dict[str, Any] = {
            "artifact_path": artifact_path,
            "artifact_type": self._artifact_type_for_path(artifact_path),
            "generator": "tool.write_file",
            "generator_version": str(manifest.get("tool_contract_version") or "1.0.0"),
            "source_hash": source_hash,
            "produced_at": produced_at,
            "truth_classification": "direct",
            "step_id": str(captured_receipt.get("step_id") or "").strip(),
            "operation_id": str(captured_receipt.get("operation_id") or "").strip(),
            "issue_id": captured_issue_id,
            "role_name": captured_role_name,
            "turn_index": captured_turn_index,
            "tool_call_hash": str(captured_receipt.get("tool_call_hash") or "").strip(),
            "receipt_digest": str(captured_receipt.get("receipt_digest") or "").strip(),
        }
        for field in (
            "control_plane_run_id",
            "control_plane_attempt_id",
            "control_plane_step_id",
        ):
            token = str(manifest.get(field) or "").strip()
            if token:
                entry[field] = token
        return entry

    async def _artifact_provenance_entry_from_log_pair(
        self,
        *,
        run_id: str,
        operation_id: str,
        start: dict[str, Any],
        workspace: Path,
    ) -> dict[str, Any] | None:
        captured_start = deepcopy(start)
        captured_workspace, = capture_file_roots([workspace])
        captured_run_id = str(run_id)
        captured_operation_id = str(operation_id)
        artifact_location = await run_owned_thread(
            partial(self._resolve_workspace_artifact_location, {},
                    {"tool_args": dict(captured_start.get("tool_args") or {})}, workspace=captured_workspace),
            label="artifact-provenance-location",
        )
        if artifact_location is None:
            return None
        artifact_path, resolved_artifact_path = artifact_location
        produced_at = await run_owned_thread(
            partial(self._artifact_produced_at, resolved_artifact_path), label="artifact-provenance-stat",
        )
        if not produced_at:
            return None
        issue_id = str(captured_start.get("issue_id") or "").strip()
        role_name = str(captured_start.get("role_name") or "").strip()
        turn_index = int(captured_start.get("turn_index") or 0)
        step_id = f"{issue_id}:{turn_index}" if issue_id and turn_index > 0 else ""
        source_hash = self._artifact_log_source_hash(
            run_id=captured_run_id,
            operation_id=captured_operation_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            tool_args=dict(captured_start.get("tool_args") or {}),
        )
        return {
            "artifact_path": artifact_path,
            "artifact_type": self._artifact_type_for_path(artifact_path),
            "generator": "tool.write_file",
            "generator_version": "unversioned",
            "source_hash": source_hash,
            "produced_at": produced_at,
            "truth_classification": "direct",
            "step_id": step_id,
            "operation_id": captured_operation_id,
            "issue_id": issue_id,
            "role_name": role_name,
            "turn_index": turn_index,
        }

    def _artifact_provenance_receipt_paths(self, run_id: str, workspace: Path) -> list[Path]:
        observability_root = workspace / "observability" / sanitize_name(run_id)
        if not observability_root.exists():
            return []
        return sorted(observability_root.rglob("protocol_receipts.log"))

    def _artifact_provenance_receipt_context(
        self, *, receipt_path: Path, run_id: str, workspace: Path,
    ) -> tuple[str, str, int]:
        session_root = workspace / "observability" / sanitize_name(run_id)
        try:
            relative_path = receipt_path.relative_to(session_root)
        except ValueError:
            return "", "", 0
        parts = relative_path.parts
        if len(parts) < 3:
            return "", "", 0
        issue_id = str(parts[0]).strip()
        turn_token = str(parts[1]).strip()
        turn_index = 0
        role_name = ""
        if "_" in turn_token:
            raw_turn_index, role_name = turn_token.split("_", 1)
            try:
                turn_index = max(0, int(raw_turn_index))
            except ValueError:
                turn_index = 0
        return issue_id, role_name.strip(), turn_index

    def _resolve_workspace_artifact_location(
        self,
        execution_result: dict[str, Any],
        receipt: dict[str, Any],
        *,
        workspace: Path,
    ) -> tuple[str, Path] | None:
        raw_path = str(execution_result.get("path") or "").strip()
        if not raw_path:
            raw_tool_args = receipt.get("tool_args")
            tool_args: dict[str, Any] = dict(raw_tool_args) if isinstance(raw_tool_args, dict) else {}
            raw_path = str(tool_args.get("path") or "").strip()
        if not raw_path:
            return None
        workspace_root = workspace.resolve()
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = workspace_root / candidate
        resolved = candidate.resolve(strict=False)
        if not resolved.is_relative_to(workspace_root):
            return None
        if not resolved.exists() or not resolved.is_file():
            return None
        return resolved.relative_to(workspace_root).as_posix(), resolved

    @staticmethod
    def _artifact_type_for_path(artifact_path: str) -> str:
        normalized = str(artifact_path or "").strip().lower()
        if normalized.endswith("/source_attribution_receipt.json"):
            return "source_attribution_receipt"
        if normalized.endswith("/requirements.txt"):
            return "requirements_document"
        if normalized.endswith("/design.txt"):
            return "design_document"
        if normalized.endswith(".py"):
            return "source_code"
        if normalized.endswith(".json"):
            return "json_document"
        if normalized.endswith(".txt") or normalized.endswith(".md"):
            return "document"
        return "file"

    @staticmethod
    def _artifact_produced_at(path: Path) -> str:
        try:
            stat_result = path.stat()
        except OSError:
            return ""
        return datetime.fromtimestamp(stat_result.st_mtime, UTC).isoformat()

    @staticmethod
    def _artifact_log_source_hash(
        *,
        run_id: str,
        operation_id: str,
        issue_id: str,
        role_name: str,
        turn_index: int,
        tool_args: dict[str, Any],
    ) -> str:
        return protocol_hashing.hash_canonical_json(
            {
                "run_id": str(run_id),
                "operation_id": str(operation_id),
                "issue_id": str(issue_id),
                "role_name": str(role_name),
                "turn_index": int(turn_index),
                "tool": "write_file",
                "tool_args": dict(tool_args),
            }
        )


def _read_optional_lines(path: Path) -> list[str] | None:
    try:
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8").split("\n")
    except OSError:
        return None
