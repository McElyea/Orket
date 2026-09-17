from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.adapters.storage.outward_store_transaction import OutwardStoreUnitOfWork
from orket.application.services.outward_control_plane_service import (
    admit_outward_run,
    outward_status_payload,
    require_outward_authority,
)
from orket.core.domain.outward_run_events import LedgerEvent
from orket.core.domain.outward_runs import OutwardRunRecord


class OutwardRunValidationError(ValueError):
    pass


class OutwardRunConflictError(RuntimeError):
    pass


class OutwardRunService:
    def __init__(
        self,
        *,
        run_store: OutwardRunStore,
        event_store: OutwardRunEventStore,
        run_id_factory: Callable[[], str],
        utc_now: Callable[[], str],
        unit_of_work: OutwardStoreUnitOfWork | None = None,
    ) -> None:
        self.run_store = run_store
        self.event_store = event_store
        self.run_id_factory = run_id_factory
        self.utc_now = utc_now
        self.unit_of_work = unit_of_work or OutwardStoreUnitOfWork.for_run_stores(run_store, event_store)

    async def submit(self, payload: Mapping[str, Any]) -> OutwardRunRecord:
        normalized = self._normalize_submission(payload)
        run_id = normalized["run_id"] or f"run-{self.run_id_factory()}"
        namespace = normalized["namespace"] or f"issue:{run_id}"
        async with self.unit_of_work.transaction() as transaction:
            existing = await transaction.get_run(run_id)
            if existing is not None:
                existing.require_execution_admission()
                if await transaction.get_event(f"run:{run_id}:submitted") is None:
                    raise OutwardRunConflictError("E_OUTWARD_ADMISSION_EVENT_MISSING")
                await require_outward_authority(transaction, existing)
                return existing
            namespace_owner = await transaction.get_active_by_namespace(namespace)
            if namespace_owner is not None:
                raise OutwardRunConflictError(f"namespace already has an active run: {namespace}")
            record = OutwardRunRecord(
                run_id=run_id,
                status="queued",
                namespace=namespace,
                submitted_at=self.utc_now(),
                current_turn=0,
                max_turns=normalized["max_turns"],
                task=normalized["task"],
                policy_overrides=normalized["policy_overrides"],
                execution_generation=1,
            )
            created = await transaction.create_run(record)
            await transaction.append_event(self._initial_event(created))
            await admit_outward_run(transaction, created)
            return created

    async def status_payload(self, run_id: str) -> dict[str, Any]:
        async with self.unit_of_work.transaction() as transaction:
            run = await transaction.get_run(run_id)
            if run is None:
                raise OutwardRunValidationError(f"Run '{run_id}' not found")
            return await outward_status_payload(transaction, run)

    async def get_status(self, run_id: str) -> OutwardRunRecord | None:
        clean_run_id = str(run_id or "").strip()
        if not clean_run_id:
            raise OutwardRunValidationError("run_id is required")
        return await self.run_store.get(clean_run_id)

    async def list_runs(self, *, status: str | None = None, limit: int = 20, offset: int = 0) -> list[OutwardRunRecord]:
        clean_status = str(status or "").strip() or None
        return await self.run_store.list(status=clean_status, limit=limit, offset=offset)

    @staticmethod
    def _initial_event(record: OutwardRunRecord) -> LedgerEvent:
        return LedgerEvent(
            event_id=f"run:{record.run_id}:submitted",
            event_type="run_submitted",
            run_id=record.run_id,
            turn=0,
            agent_id="operator",
            at=record.submitted_at,
            payload={
                "run_id": record.run_id,
                "namespace": record.namespace,
                "status": record.status,
                "submitted_at": record.submitted_at,
                "task_description": str(record.task.get("description") or ""),
                "policy_overrides": dict(record.policy_overrides),
            },
        )

    @staticmethod
    def _normalize_submission(payload: Mapping[str, Any]) -> dict[str, Any]:
        raw_task = payload.get("task")
        if not isinstance(raw_task, Mapping):
            raise OutwardRunValidationError("task is required")
        description = str(raw_task.get("description") or "").strip()
        instruction = str(raw_task.get("instruction") or "").strip()
        if not description:
            raise OutwardRunValidationError("task.description is required")
        if not instruction:
            raise OutwardRunValidationError("task.instruction is required")
        acceptance_contract = raw_task.get("acceptance_contract", {})
        if acceptance_contract is None:
            acceptance_contract = {}
        if not isinstance(acceptance_contract, Mapping):
            raise OutwardRunValidationError("task.acceptance_contract must be an object")

        policy_overrides = _normalize_policy_overrides(payload.get("policy_overrides", {}))
        max_turns = int(policy_overrides.get("max_turns", 20))
        return {
            "run_id": str(payload.get("run_id") or "").strip(),
            "namespace": str(payload.get("namespace") or "").strip(),
            "task": {
                "description": description,
                "instruction": instruction,
                "acceptance_contract": dict(acceptance_contract),
            },
            "policy_overrides": policy_overrides,
            "max_turns": max_turns,
        }


def _normalize_policy_overrides(raw: Any) -> dict[str, Any]:
    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping):
        raise OutwardRunValidationError("policy_overrides must be an object")
    normalized: dict[str, Any] = {}
    if "approval_required_tools" in raw:
        tools = raw["approval_required_tools"]
        if not isinstance(tools, list) or not all(str(item).strip() for item in tools):
            raise OutwardRunValidationError("policy_overrides.approval_required_tools must be a list of tool names")
        normalized["approval_required_tools"] = [str(item).strip() for item in tools]
    if "max_turns" in raw:
        normalized["max_turns"] = _positive_int(raw["max_turns"], "policy_overrides.max_turns")
    if "approval_timeout_seconds" in raw:
        normalized["approval_timeout_seconds"] = _positive_int(
            raw["approval_timeout_seconds"],
            "policy_overrides.approval_timeout_seconds",
        )
    return normalized


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise OutwardRunValidationError(f"{field} must be a positive integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise OutwardRunValidationError(f"{field} must be a positive integer") from exc
    if parsed <= 0:
        raise OutwardRunValidationError(f"{field} must be a positive integer")
    return parsed


__all__ = ["OutwardRunConflictError", "OutwardRunService", "OutwardRunValidationError"]
