from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiofiles

from orket.core.cards_runtime_contract import (
    DEFAULT_RUNTIME_VERIFICATION_INDEX_PATH,
    DEFAULT_RUNTIME_VERIFICATION_PATH,
    DEFAULT_RUNTIME_VERIFICATION_RECORDS_DIR,
)
from orket.utils import sanitize_name

_LATEST_SCHEMA_VERSION = "runtime_verification.latest.v2"
_INDEX_SCHEMA_VERSION = "runtime_verification.index.v1"
_ARTIFACT_ROLE = "support_verification_evidence"
_ARTIFACT_AUTHORITY = "support_only"
_INDEX_ARTIFACT_ROLE = "support_verification_history_index"
_ALLOWED_EVIDENCE_CLASSES = {
    "syntax_only",
    "command_execution",
    "behavioral_verification",
    "not_evaluated",
}


@dataclass(frozen=True)
class RuntimeVerificationArtifactContext:
    run_id: str
    issue_id: str
    turn_index: int
    retry_count: int
    seat_name: str
    recorded_at: str


@dataclass(frozen=True)
class RuntimeVerificationArtifactWriteResult:
    latest_path: str
    index_path: str
    record_path: str
    record_id: str


class RuntimeVerificationArtifactService:
    """Persists truthful runtime-verifier support artifacts with preserved history."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = Path(workspace_root)

    async def write(
        self,
        *,
        context: RuntimeVerificationArtifactContext,
        runtime_result: Any,
        guard_contract: dict[str, Any],
        guard_decision: dict[str, Any],
    ) -> RuntimeVerificationArtifactWriteResult:
        record_id = self._record_id(context)
        record_path = self._record_path(context)
        latest_path = self.workspace_root / DEFAULT_RUNTIME_VERIFICATION_PATH
        index_path = self.workspace_root / DEFAULT_RUNTIME_VERIFICATION_INDEX_PATH
        record_rel = self._relative_path(record_path)
        latest_rel = self._relative_path(latest_path)
        index_rel = self._relative_path(index_path)

        payload = self._build_payload(
            context=context,
            runtime_result=runtime_result,
            guard_contract=guard_contract,
            guard_decision=guard_decision,
            record_id=record_id,
            record_path=record_rel,
            latest_path=latest_rel,
            index_path=index_rel,
        )
        await self._write_json(record_path, payload)
        await self._write_json(latest_path, payload)

        index_payload = await self._build_index_payload(
            context=context,
            payload=payload,
            record_id=record_id,
            record_rel=record_rel,
            latest_rel=latest_rel,
            index_rel=index_rel,
            index_path=index_path,
        )
        await self._write_json(index_path, index_payload)
        return RuntimeVerificationArtifactWriteResult(
            latest_path=latest_rel,
            index_path=index_rel,
            record_path=record_rel,
            record_id=record_id,
        )

    async def _build_index_payload(
        self,
        *,
        context: RuntimeVerificationArtifactContext,
        payload: dict[str, Any],
        record_id: str,
        record_rel: str,
        latest_rel: str,
        index_rel: str,
        index_path: Path,
    ) -> dict[str, Any]:
        existing = await self._read_json_object(index_path)
        raw_records = list(existing.get("records") or []) if isinstance(existing, dict) else []
        records = [dict(item) for item in raw_records if isinstance(item, dict)]
        records = [row for row in records if str(row.get("record_id") or "").strip() != record_id]
        records.append(
            {
                "record_id": record_id,
                "record_path": record_rel,
                "run_id": context.run_id,
                "issue_id": context.issue_id,
                "turn_index": int(context.turn_index),
                "retry_count": int(context.retry_count),
                "seat_name": context.seat_name,
                "recorded_at": context.recorded_at,
                "ok": bool(payload.get("ok", False)),
                "overall_evidence_class": str(payload.get("overall_evidence_class") or "not_evaluated"),
            }
        )
        records.sort(
            key=lambda item: (
                str(item.get("run_id") or ""),
                str(item.get("issue_id") or ""),
                int(item.get("turn_index") or 0),
                int(item.get("retry_count") or 0),
                str(item.get("recorded_at") or ""),
            )
        )
        return {
            "schema_version": _INDEX_SCHEMA_VERSION,
            "artifact_role": _INDEX_ARTIFACT_ROLE,
            "artifact_authority": _ARTIFACT_AUTHORITY,
            "authored_output": False,
            "latest_path": latest_rel,
            "latest_record_id": record_id,
            "latest_record_path": record_rel,
            "index_path": index_rel,
            "history_count": len(records),
            "records": records,
        }

    def _build_payload(
        self,
        *,
        context: RuntimeVerificationArtifactContext,
        runtime_result: Any,
        guard_contract: dict[str, Any],
        guard_decision: dict[str, Any],
        record_id: str,
        record_path: str,
        latest_path: str,
        index_path: str,
    ) -> dict[str, Any]:
        overall_evidence_class = str(getattr(runtime_result, "overall_evidence_class", "") or "not_evaluated").strip()
        if overall_evidence_class not in _ALLOWED_EVIDENCE_CLASSES:
            overall_evidence_class = "not_evaluated"
        evidence_summary = getattr(runtime_result, "evidence_summary", None)
        evidence_summary_payload = dict(evidence_summary) if isinstance(evidence_summary, dict) else {
            "syntax_only": {"evaluated": False, "checked_files": [], "commands": []},
            "command_execution": {"evaluated": False, "commands": []},
            "behavioral_verification": {
                "evaluated": False,
                "stdout_contract_requested": False,
                "json_assertion_count": 0,
                "commands": [],
            },
            "not_evaluated": [
                {
                    "check": "behavioral_verification",
                    "reason": "runtime verifier result did not provide an evidence summary",
                }
            ],
        }
        return {
            "schema_version": _LATEST_SCHEMA_VERSION,
            "artifact_role": _ARTIFACT_ROLE,
            "artifact_authority": _ARTIFACT_AUTHORITY,
            "authored_output": False,
            "ok": bool(getattr(runtime_result, "ok", False)),
            "overall_evidence_class": overall_evidence_class,
            "evidence_summary": evidence_summary_payload,
            "checked_files": list(getattr(runtime_result, "checked_files", []) or []),
            "errors": list(getattr(runtime_result, "errors", []) or []),
            "command_results": [dict(item) for item in list(getattr(runtime_result, "command_results", []) or [])],
            "failure_breakdown": dict(getattr(runtime_result, "failure_breakdown", {}) or {}),
            "guard_contract": dict(guard_contract or {}),
            "guard_decision": dict(guard_decision or {}),
            "provenance": {
                "run_id": context.run_id,
                "issue_id": context.issue_id,
                "turn_index": int(context.turn_index),
                "retry_count": int(context.retry_count),
                "seat_name": context.seat_name,
                "recorded_at": context.recorded_at,
                "record_id": record_id,
            },
            "history": {
                "latest_path": latest_path,
                "index_path": index_path,
                "record_path": record_path,
            },
        }

    def _record_id(self, context: RuntimeVerificationArtifactContext) -> str:
        return (
            f"runtime-verification:{sanitize_name(context.run_id)}:{sanitize_name(context.issue_id)}"
            f":turn:{int(context.turn_index):04d}:retry:{int(context.retry_count):04d}"
        )

    def _record_path(self, context: RuntimeVerificationArtifactContext) -> Path:
        run_dir = sanitize_name(context.run_id) or "unknown_run"
        issue_dir = sanitize_name(context.issue_id) or "unknown_issue"
        filename = f"turn_{int(context.turn_index):04d}_retry_{int(context.retry_count):04d}.json"
        return self.workspace_root / DEFAULT_RUNTIME_VERIFICATION_RECORDS_DIR / run_dir / issue_dir / filename

    def _relative_path(self, path: Path) -> str:
        return path.resolve().relative_to(self.workspace_root.resolve()).as_posix()

    async def _read_json_object(self, path: Path) -> dict[str, Any]:
        exists = await asyncio.to_thread(path.exists)
        if not exists:
            return {}
        try:
            async with aiofiles.open(path, encoding="utf-8") as handle:
                payload = json.loads(await handle.read())
        except (OSError, ValueError, TypeError):
            return {}
        return dict(payload) if isinstance(payload, dict) else {}

    async def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        content = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
        async with aiofiles.open(path, mode="w", encoding="utf-8") as handle:
            await handle.write(content)
