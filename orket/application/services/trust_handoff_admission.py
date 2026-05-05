from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from typing import Any

from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.application.services.trust_handoff_contract import failure_class
from orket.application.services.trust_handoff_verifier import (
    TrustHandoffVerificationContext,
    verify_trust_handoff_package,
)
from orket.core.domain.outward_run_events import LedgerEvent
from orket.core.domain.outward_runs import OutwardRunRecord


class TrustHandoffAdmissionService:
    def __init__(
        self,
        *,
        run_store: OutwardRunStore,
        event_store: OutwardRunEventStore,
        utc_now: Any,
    ) -> None:
        self.run_store = run_store
        self.event_store = event_store
        self.utc_now = utc_now

    async def admit_if_required(self, run: OutwardRunRecord) -> tuple[OutwardRunRecord, bool]:
        acceptance = _acceptance_contract(run)
        if acceptance.get("handoff_required") is not True:
            return run, True
        missing = _missing_acceptance_fields(acceptance)
        if missing:
            report = _rejection_report("handoff_acceptance_contract_incomplete", detail=",".join(missing))
            return await self._reject(run, report, _package_path(acceptance)), False

        package_path = _package_path(acceptance)
        context = TrustHandoffVerificationContext(
            expected_scope_id=str(acceptance.get("handoff_policy_compatibility_scope_id") or ""),
            expected_source_agent_id=str(acceptance.get("expected_source_agent_id") or ""),
            expected_target_agent_id=run.run_id,
        )
        report = await asyncio.to_thread(verify_trust_handoff_package, package_path, context=context)
        if report.get("result") != "accepted":
            return await self._reject(run, report, package_path), False
        await self._append_once(
            event_id=f"run:{run.run_id}:0050:trust_handoff_verified",
            event_type="trust_handoff_verified",
            run=run,
            payload=_verified_payload(report, package_path),
        )
        return run, True

    async def _reject(self, run: OutwardRunRecord, report: dict[str, Any], package_path: Path) -> OutwardRunRecord:
        now = self.utc_now()
        rejected = replace(run, status="completed", pending_proposals=(), completed_at=now, stop_reason=str(report.get("rejection_reason") or "trust_handoff_rejected"))
        await self.run_store.update(rejected)
        await self._append_once(
            event_id=f"run:{run.run_id}:0050:trust_handoff_rejected",
            event_type="trust_handoff_rejected",
            run=rejected,
            payload=_rejected_payload(report, package_path),
        )
        await self._append_once(
            event_id=f"run:{run.run_id}:0060:handoff_rejected:completed",
            event_type="run_completed",
            run=rejected,
            payload={
                "run_id": run.run_id,
                "status": "completed",
                "outcome": "handoff_rejected",
                "result_class": "handoff_rejected",
                "evidence_sufficiency": "evidence_sufficient",
                "rejection_reason": report.get("rejection_reason"),
                "rejection_class": report.get("rejection_class"),
                "completed_at": now,
            },
        )
        return rejected

    async def _append_once(
        self,
        *,
        event_id: str,
        event_type: str,
        run: OutwardRunRecord,
        payload: dict[str, Any],
    ) -> None:
        if await self.event_store.get(event_id) is not None:
            return
        await self.event_store.append(
            LedgerEvent(
                event_id=event_id,
                event_type=event_type,
                run_id=run.run_id,
                turn=0,
                agent_id="outward-agent",
                at=self.utc_now(),
                payload=payload,
            )
        )


def _acceptance_contract(run: OutwardRunRecord) -> dict[str, Any]:
    acceptance = run.task.get("acceptance_contract")
    return dict(acceptance) if isinstance(acceptance, dict) else {}


def _missing_acceptance_fields(acceptance: dict[str, Any]) -> list[str]:
    required = ("handoff_policy_compatibility_scope_id", "handoff_envelope_package_path", "expected_source_agent_id")
    return [field for field in required if not str(acceptance.get(field) or "").strip()]


def _package_path(acceptance: dict[str, Any]) -> Path:
    return Path(str(acceptance.get("handoff_envelope_package_path") or ""))


def _rejection_report(reason: str, *, detail: str | None = None) -> dict[str, Any]:
    return {
        "result": "rejected",
        "rejection_reason": reason,
        "rejection_class": failure_class(reason),
        "failure_detail": detail,
    }


def _verified_payload(report: dict[str, Any], package_path: Path) -> dict[str, Any]:
    output = report.get("source_output_anchor_result") if isinstance(report.get("source_output_anchor_result"), dict) else {}
    policy = report.get("source_policy_anchor_result") if isinstance(report.get("source_policy_anchor_result"), dict) else {}
    compatibility = report.get("policy_compatibility_result") if isinstance(report.get("policy_compatibility_result"), dict) else {}
    return {
        "bundle_id": report.get("bundle_id"),
        "source_run_id": report.get("source_run_id"),
        "source_agent_id": report.get("source_agent_id"),
        "committed_output_digest": output.get("committed_output_digest"),
        "source_policy_digest": policy.get("source_policy_digest"),
        "handoff_policy_compatibility_scope_id": compatibility.get("scope_id"),
        "envelope_digest": report.get("envelope_digest"),
        "package_path": str(package_path),
    }


def _rejected_payload(report: dict[str, Any], package_path: Path) -> dict[str, Any]:
    return {
        "rejection_reason": report.get("rejection_reason"),
        "rejection_class": report.get("rejection_class"),
        "bundle_id": report.get("bundle_id"),
        "source_run_id": report.get("source_run_id"),
        "package_path": str(package_path) if str(package_path) else None,
        "result_class": "handoff_rejected",
        "evidence_sufficiency": "evidence_sufficient",
    }
