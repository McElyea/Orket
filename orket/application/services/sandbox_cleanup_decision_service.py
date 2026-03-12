from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from orket.application.services.sandbox_cleanup_authority_service import CleanupAuthorityDecision
from orket.application.services.sandbox_lifecycle_event_publisher import SandboxLifecycleEventPublisher
from orket.core.domain.sandbox_cleanup import ObservedDockerResource
from orket.core.domain.sandbox_lifecycle import SandboxState, TerminalReason
from orket.core.domain.sandbox_lifecycle_records import SandboxLifecycleRecord


@dataclass(frozen=True)
class SandboxCleanupDecision:
    sandbox_id: str
    compose_project: str
    reason_code: str
    policy_match: str
    dry_run: bool
    cleanup_strategy: str
    cleanup_result: str
    compose_path_available: bool
    observed_resource_names: list[str]
    authority_reason_codes: list[str]
    fallback_resource_names: list[str]
    blocked_resource_names: list[str]

    def to_payload(self) -> dict[str, object]:
        return {
            "sandbox_id": self.sandbox_id,
            "compose_project": self.compose_project,
            "reason_code": self.reason_code,
            "policy_match": self.policy_match,
            "dry_run": self.dry_run,
            "cleanup_strategy": self.cleanup_strategy,
            "cleanup_result": self.cleanup_result,
            "compose_path_available": self.compose_path_available,
            "observed_resource_names": self.observed_resource_names,
            "authority_reason_codes": self.authority_reason_codes,
            "fallback_resource_names": self.fallback_resource_names,
            "blocked_resource_names": self.blocked_resource_names,
        }


class SandboxCleanupDecisionService:
    """Builds and emits deterministic cleanup decisions for dry-run and execute paths."""

    def __init__(self, *, event_publisher: SandboxLifecycleEventPublisher) -> None:
        self.event_publisher = event_publisher

    def build_decision(
        self,
        *,
        record: SandboxLifecycleRecord,
        compose_path: Path,
        observed_resources: list[ObservedDockerResource],
        authority: CleanupAuthorityDecision,
        dry_run: bool,
    ) -> SandboxCleanupDecision:
        strategy = "blocked"
        result = "blocked"
        if authority.compose_cleanup_allowed:
            strategy = "compose"
            result = "would_execute_compose" if dry_run else "execute_compose"
        elif authority.fallback_resource_names:
            strategy = "fallback"
            result = "would_execute_fallback" if dry_run else "execute_fallback"
        return SandboxCleanupDecision(
            sandbox_id=record.sandbox_id,
            compose_project=record.compose_project,
            reason_code=(record.terminal_reason or TerminalReason.CANCELED).value,
            policy_match=self._policy_match(record),
            dry_run=dry_run,
            cleanup_strategy=strategy,
            cleanup_result=result,
            compose_path_available=compose_path.exists(),
            observed_resource_names=sorted(resource.name for resource in observed_resources),
            authority_reason_codes=authority.reason_codes,
            fallback_resource_names=authority.fallback_resource_names,
            blocked_resource_names=authority.blocked_resource_names,
        )

    async def emit_decision(self, *, decision: SandboxCleanupDecision, observed_at: str) -> str:
        return await self.event_publisher.emit(
            sandbox_id=decision.sandbox_id,
            created_at=observed_at,
            event_type="sandbox.cleanup_decision_evaluated",
            payload=decision.to_payload(),
            event_kind="cleanup",
        )

    async def emit_execution_result(
        self,
        *,
        decision: SandboxCleanupDecision,
        observed_at: str,
        cleanup_result: str,
        error: str | None = None,
    ) -> str:
        payload = decision.to_payload()
        payload["dry_run"] = False
        payload["cleanup_result"] = cleanup_result
        if error:
            payload["error"] = error
        return await self.event_publisher.emit(
            sandbox_id=decision.sandbox_id,
            created_at=observed_at,
            event_type="sandbox.cleanup_execution_result",
            payload=payload,
            event_kind="cleanup",
        )

    @staticmethod
    def _policy_match(record: SandboxLifecycleRecord) -> str:
        if record.state is SandboxState.ORPHANED:
            if record.terminal_reason is TerminalReason.ORPHAN_DETECTED:
                return "verified_orphan_cleanup_due"
            return "unverified_orphan_quarantine"
        return "terminal_cleanup_due"
