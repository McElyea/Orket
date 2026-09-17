from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket.application.services.card_completion_outcome_service import BuildCompletionSnapshot, inspect_build_completion
from orket.application.services.epic_preparation_service import EpicPreparationService
from orket.application.services.epic_publication_service import EpicPublicationService
from orket.application.services.epic_workload_outcome_service import EpicWorkloadOutcomeService
from orket.core.cards_runtime_contract import normalize_scenario_truth_alignment, summarize_cards_runtime_issues
from orket.core.contracts.epic_publication import EpicPublicationPlan, EpicWorkloadFailure, EpicWorkloadOutcome
from orket.core.contracts.repositories import CardRepository
from orket.core.contracts.runtime_execution_result import RuntimeExecutionResult
from orket.core.domain.records import IssueRecord
from orket.logging import log_event
from orket.runtime.epic_run_support import (
    WORKFLOW_TERMINAL_STATUSES,
    await_infrastructure,
    build_execution_artifacts,
    build_legacy_transcript,
)
from orket.runtime.epic_run_types import (
    EpicRunCallbacks,
    EpicRunContext,
)
from orket.runtime.phase_c_runtime_truth import (
    collect_source_attribution_facts,
    resolve_source_attribution_gate_failure_reason,
)
from orket.runtime.state_transition_registry import validate_state_token


@dataclass(frozen=True)
class EpicRunFinalizer:
    workspace: Path
    cards_repo: CardRepository
    cards_epic_control_plane: Any
    publication: EpicPublicationService
    preparation: EpicPreparationService
    outcomes: EpicWorkloadOutcomeService
    callbacks: EpicRunCallbacks

    async def recover(self, session_id: str, request: dict[str, Any]) -> RuntimeExecutionResult | None:
        outcome = await self.outcomes.read(session_id, request, self.preparation.export_binding)
        if outcome is None:
            return None
        # Another reentry may have advanced preparation since the first journal read.
        await self.preparation.recover(session_id, request)
        published = await self.publication.recover(session_id, request)
        if published is not None:
            return published
        return await self.finalize_outcome(outcome)

    async def finalize_success(self, *, context: EpicRunContext, transcript: list[Any]) -> RuntimeExecutionResult:
        return await self.finalize_outcome(await self.retain_outcome(context, transcript))

    async def finalize_failure(self, *, context: EpicRunContext, transcript: list[Any], exc: Exception) -> RuntimeExecutionResult:
        return await self.finalize_outcome(await self.retain_outcome(context, transcript, exc))

    async def retain_outcome(self, context: EpicRunContext, transcript: list[Any],
                              exc: Exception | None = None) -> EpicWorkloadOutcome:
        artifacts = build_execution_artifacts(callbacks=self.callbacks, context=context)
        return await self.outcomes.retain(EpicWorkloadOutcome(
            session_id=context.setup.run_id, request=context.setup.publication_request,
            policy=context.setup.phase_c_truth_policy, export_binding=self.preparation.export_binding,
            artifacts=artifacts, transcript=build_legacy_transcript(transcript), observed_at=self.preparation.now(),
            snapshot={"epic": context.setup.epic.model_dump(), "team": context.setup.team.model_dump(),
                      "env": context.setup.env.model_dump(), "build_id": context.setup.build_id},
            failure=EpicWorkloadFailure(reason=str(exc)[:2000], failure_class=type(exc).__name__) if exc else None))

    async def finalize_outcome(self, outcome: EpicWorkloadOutcome) -> RuntimeExecutionResult:
        artifacts = outcome.model_copy(deep=True).artifacts
        if outcome.failure is not None:
            return await self._prepare_and_publish(
                outcome=outcome, status="failed", failure_reason=outcome.failure.reason,
                failure_class=outcome.failure.failure_class, artifacts=artifacts, snapshot=None)
        completion = await await_infrastructure(
            "inspect epic completion",
            inspect_build_completion(cards=self.cards_repo, build_id=outcome.request["build_id"],
                                     expected_card_ids=tuple(i["id"] for i in outcome.request["epic"]["issues"])))
        backlog = list(completion.backlog)
        artifacts["card_completion_outcome"] = completion.to_artifact()
        session_status, failure_reason, is_workflow_terminal = await self._resolve_success_outcome(
            outcome=outcome, completion=completion)
        cards_summary = self._cards_runtime_summary(backlog=backlog, session_status=session_status)
        if cards_summary:
            artifacts["cards_runtime_facts"] = cards_summary
        request = outcome.request
        result = await self._prepare_and_publish(
            outcome=outcome, status=session_status, failure_reason=failure_reason, artifacts=artifacts,
            snapshot=outcome.snapshot)
        self._log_backlog_state(run_id=outcome.session_id, build_id=request["build_id"],
                                session_status=session_status, failure_reason=failure_reason,
                                backlog=backlog, is_workflow_terminal=is_workflow_terminal)
        return result

    async def _prepare_and_publish(self, *, outcome: EpicWorkloadOutcome, status: str, failure_reason: str | None,
                                   artifacts: dict[str, Any], snapshot: dict[str, Any] | None,
                                   failure_class: str | None = None) -> RuntimeExecutionResult:
        plan = EpicPublicationPlan(
            session_id=outcome.session_id, request=outcome.request,
            ledger={"session_id": outcome.session_id, "status": validate_state_token(domain="session", state=status),
                    "failure_reason": failure_reason, "failure_class": failure_class, "summary": {},
                    "artifacts": artifacts, "finalized_at": outcome.observed_at},
            transcript=outcome.transcript, snapshot=snapshot)
        prepared = await self.preparation.prepare(plan, policy=outcome.policy)
        return await self.publication.publish(prepared)

    async def _resolve_success_outcome(
        self, *, outcome: EpicWorkloadOutcome, completion: BuildCompletionSnapshot,
    ) -> tuple[str, str | None, bool]:
        is_workflow_terminal = bool(completion.backlog) and all(i.status in WORKFLOW_TERMINAL_STATUSES for i in completion.backlog)
        session_status = "done" if completion.sufficient else "terminal_failure" if is_workflow_terminal else "incomplete"
        failure_reason = await self._resolve_source_attribution_failure(outcome=outcome, session_status=session_status)
        if session_status == "done" and failure_reason is not None:
            session_status = "terminal_failure"
        failure_reason = failure_reason or (completion.failure_reason if session_status == "terminal_failure" else None)
        return validate_state_token(domain="session", state=session_status), failure_reason, is_workflow_terminal

    async def _resolve_source_attribution_failure(self, *, outcome: EpicWorkloadOutcome, session_status: str) -> str | None:
        source_attribution_facts = await await_infrastructure(
            "collect source attribution facts", collect_source_attribution_facts(workspace=self.workspace, policy=outcome.policy))
        failure_reason = resolve_source_attribution_gate_failure_reason(source_attribution_facts)
        if session_status == "done" and failure_reason is not None:
            log_event(
                "source_attribution_gate_blocked",
                {"run_id": outcome.session_id, "failure_reason": failure_reason,
                 "mode": source_attribution_facts.get("mode"),
                 "missing_requirements": list(source_attribution_facts.get("missing_requirements") or [])},
                workspace=self.workspace)
        return failure_reason

    def _log_backlog_state(
        self,
        *,
        run_id: str,
        build_id: str,
        session_status: str,
        failure_reason: str | None,
        backlog: list[IssueRecord],
        is_workflow_terminal: bool,
    ) -> None:
        if not is_workflow_terminal:
            log_event(
                "session_incomplete",
                {
                    "run_id": run_id,
                    "build_id": build_id,
                    "open_issues": [{"id": i.id, "status": i.status.value} for i in backlog if i.status not in WORKFLOW_TERMINAL_STATUSES],
                },
                workspace=self.workspace,
            )
            return
        if session_status == "terminal_failure":
            log_event(
                "session_terminal_failure",
                {
                    "run_id": run_id,
                    "build_id": build_id,
                    "issues": [{"id": i.id, "status": i.status.value} for i in backlog],
                    "failure_reason": failure_reason,
                },
                workspace=self.workspace,
            )

    def _cards_runtime_summary(self, *, backlog: list[IssueRecord], session_status: str) -> dict[str, Any]:
        summary = summarize_cards_runtime_issues(
            [
                {"issue_id": issue.id, **issue.params["cards_runtime_summary"]}
                for issue in backlog
                if isinstance(issue.params.get("cards_runtime_summary"), dict)
            ]
        )
        if not summary:
            return {}
        alignment = normalize_scenario_truth_alignment(
            scenario_truth=summary.get("scenario_truth"),
            observed_terminal_status=session_status,
        )
        if alignment:
            summary["scenario_truth_alignment"] = alignment
        summary["resolution_state"] = "resolved"
        return summary
