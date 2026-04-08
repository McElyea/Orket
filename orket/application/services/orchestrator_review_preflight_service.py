from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from orket.application.services.guard_agent import GuardAgent
from orket.application.services.runtime_verification_artifact_service import (
    RuntimeVerificationArtifactContext,
    RuntimeVerificationArtifactService,
)
from orket.application.services.runtime_verifier import build_runtime_guard_contract
from orket.logging import log_event
from orket.orchestration.notes import Note
from orket.schema import CardStatus, IssueConfig


@dataclass
class ReviewTurnPreflightResult:
    runtime_result: Any | None
    stop_execution: bool


class OrchestratorReviewPreflightService:
    """Owns review-turn runtime verification and empirical verification gating."""

    def __init__(
        self,
        *,
        workspace_root: Path,
        organization: Any,
        support_services: Any,
        async_cards: Any,
        notes: Any,
        transcript: list[Any],
        request_issue_transition: Callable[..., Awaitable[None]],
        verify_issue: Callable[..., Awaitable[Any]],
        resolve_project_surface_profile: Callable[[], str],
        resolve_architecture_pattern: Callable[[], str | None],
        is_runtime_verifier_disabled: Callable[[], bool],
        set_issue_runtime_retry_note: Callable[[IssueConfig, str | None], None],
        clear_issue_runtime_retry_note: Callable[[IssueConfig], None],
    ) -> None:
        self.workspace_root = workspace_root
        self.organization = organization
        self.support_services = support_services
        self.async_cards = async_cards
        self.notes = notes
        self.transcript = transcript
        self.request_issue_transition = request_issue_transition
        self.verify_issue = verify_issue
        self.resolve_project_surface_profile = resolve_project_surface_profile
        self.resolve_architecture_pattern = resolve_architecture_pattern
        self.is_runtime_verifier_disabled = is_runtime_verifier_disabled
        self.set_issue_runtime_retry_note = set_issue_runtime_retry_note
        self.clear_issue_runtime_retry_note = clear_issue_runtime_retry_note

    async def run(
        self,
        *,
        issue: IssueConfig,
        run_id: str,
        is_review_turn: bool,
        cards_runtime: dict[str, Any],
    ) -> ReviewTurnPreflightResult:
        runtime_result = None
        if is_review_turn and not self.is_runtime_verifier_disabled():
            turn_index = len(self.transcript) + 1
            log_event(
                "runtime_verifier_started",
                {"run_id": run_id, "issue_id": issue.id, "turn_index": turn_index},
                self.workspace_root,
            )
            runtime_verifier = self.support_services.create_runtime_verifier(
                workspace_root=self.workspace_root,
                organization=self.organization,
                project_surface_profile=self.resolve_project_surface_profile(),
                architecture_pattern=self.resolve_architecture_pattern(),
                artifact_contract=dict(cards_runtime.get("artifact_contract") or {}),
                issue_params=dict(getattr(issue, "params", {}) or {}),
            )
            runtime_result = await runtime_verifier.verify()
            guard_contract = getattr(runtime_result, "guard_contract", None)
            if guard_contract is None:
                guard_contract = build_runtime_guard_contract(
                    ok=bool(getattr(runtime_result, "ok", False)),
                    errors=list(getattr(runtime_result, "errors", []) or []),
                )
            existing_fingerprints = []
            if isinstance(getattr(issue, "params", None), dict):
                raw_fingerprints = issue.params.get("guard_retry_fingerprints", [])
                if isinstance(raw_fingerprints, list):
                    existing_fingerprints = [str(item).strip() for item in raw_fingerprints if str(item).strip()]
            guard_decision = GuardAgent(self.organization).evaluate(
                contract=guard_contract,
                retry_count=int(getattr(issue, "retry_count", 0) or 0),
                max_retries=int(getattr(issue, "max_retries", 0) or 0),
                output_text="\n".join(list(getattr(runtime_result, "errors", []) or [])),
                seen_fingerprints=existing_fingerprints,
            )
            if not isinstance(getattr(issue, "params", None), dict):
                issue.params = {}
            issue.params["guard_retry_fingerprints"] = existing_fingerprints[-10:]
            recorded_at = datetime.now(UTC).isoformat()
            artifact_writer = RuntimeVerificationArtifactService(self.workspace_root)
            await artifact_writer.write(
                context=RuntimeVerificationArtifactContext(
                    run_id=run_id,
                    issue_id=issue.id,
                    turn_index=turn_index,
                    retry_count=int(getattr(issue, "retry_count", 0) or 0),
                    seat_name=str(getattr(issue, "seat", "") or "").strip(),
                    recorded_at=recorded_at,
                ),
                runtime_result=runtime_result,
                guard_contract=guard_contract.model_dump(),
                guard_decision=guard_decision.as_dict(),
            )
            log_event(
                "runtime_verifier_completed",
                {
                    "run_id": run_id,
                    "issue_id": issue.id,
                    "turn_index": turn_index,
                    "ok": runtime_result.ok,
                    "checked_files": len(runtime_result.checked_files),
                    "errors": len(runtime_result.errors),
                    "failure_breakdown": dict(getattr(runtime_result, "failure_breakdown", {}) or {}),
                    "overall_evidence_class": str(
                        getattr(runtime_result, "overall_evidence_class", "") or "not_evaluated"
                    ),
                },
                self.workspace_root,
            )
            if not runtime_result.ok:
                if guard_decision.action == "retry":
                    issue.retry_count = guard_decision.next_retry_count
                    self.set_issue_runtime_retry_note(
                        issue,
                        "runtime_guard_retry_scheduled: " + " | ".join(runtime_result.errors[:3]),
                    )
                    await self.request_issue_transition(
                        issue=issue,
                        target_status=CardStatus.READY,
                        reason="runtime_guard_retry_scheduled",
                        metadata={"run_id": run_id, "retry_count": issue.retry_count},
                    )
                    await self.async_cards.save(issue.model_dump())
                    log_event(
                        "guard_retry_scheduled",
                        {
                            "run_id": run_id,
                            "issue_id": issue.id,
                            "retry_count": issue.retry_count,
                            "max_retries": issue.max_retries,
                            "reason": "runtime_verification_failed",
                            "guard_contract": guard_contract.model_dump(),
                            "guard_decision": guard_decision.as_dict(),
                        },
                        self.workspace_root,
                    )
                    self.notes.add(
                        Note(
                            from_role="system",
                            content="RUNTIME VERIFIER FAILED (RETRY): " + " | ".join(runtime_result.errors[:2]),
                            step_index=len(self.transcript),
                        )
                    )
                else:
                    self.clear_issue_runtime_retry_note(issue)
                    issue.note = "runtime_guard_terminal_failure: " + (
                        guard_decision.terminal_reason.code if guard_decision.terminal_reason else "unknown"
                    )
                    await self.request_issue_transition(
                        issue=issue,
                        target_status=CardStatus.BLOCKED,
                        reason="runtime_guard_terminal_failure",
                        metadata={"run_id": run_id},
                    )
                    await self.async_cards.save(issue.model_dump())
                    log_event(
                        "guard_terminal_failure",
                        {
                            "run_id": run_id,
                            "issue_id": issue.id,
                            "retry_count": issue.retry_count,
                            "max_retries": issue.max_retries,
                            "reason": "runtime_verification_failed",
                            "guard_contract": guard_contract.model_dump(),
                            "guard_decision": guard_decision.as_dict(),
                        },
                        self.workspace_root,
                    )
                    self.notes.add(
                        Note(
                            from_role="system",
                            content="RUNTIME VERIFIER TERMINAL FAILURE: " + " | ".join(runtime_result.errors[:2]),
                            step_index=len(self.transcript),
                        )
                    )
                return ReviewTurnPreflightResult(runtime_result=runtime_result, stop_execution=True)
            self.clear_issue_runtime_retry_note(issue)

        if is_review_turn:
            verification_contract = getattr(issue, "verification", None)
            fixture_path = str(getattr(verification_contract, "fixture_path", "") or "").strip()
            scenarios = getattr(verification_contract, "scenarios", None) or []
            if fixture_path or scenarios:
                verification_result = await self.verify_issue(issue.id, run_id=run_id)
                self.notes.add(
                    Note(
                        from_role="system",
                        content=(
                            "EMPIRICAL VERIFICATION RESULT: "
                            f"{verification_result.passed}/{verification_result.total_scenarios} Passed."
                        ),
                        step_index=len(self.transcript),
                    )
                )

        return ReviewTurnPreflightResult(runtime_result=runtime_result, stop_execution=False)
