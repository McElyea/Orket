from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from orket.core.cards_runtime_contract import normalize_scenario_truth_alignment, summarize_cards_runtime_issues
from orket.exceptions import OrketInfrastructureError
from orket.logging import log_event
from orket.runtime.epic_run_support import (
    SUCCESS_STATUSES,
    WORKFLOW_TERMINAL_STATUSES,
    await_infrastructure,
    build_base_run_artifacts,
    build_legacy_transcript,
    set_control_plane_artifacts,
)
from orket.runtime.epic_run_types import (
    CardsRepository,
    EpicRunCallbacks,
    EpicRunContext,
    RunLedger,
    SessionsRepository,
    SnapshotsRepository,
    SuccessRepository,
)
from orket.runtime.phase_c_runtime_truth import (
    collect_source_attribution_facts,
    resolve_source_attribution_gate_failure_reason,
)
from orket.runtime.state_transition_registry import validate_state_token


@dataclass(frozen=True)
class EpicRunFinalizer:
    workspace: Path
    cards_repo: CardsRepository
    sessions_repo: SessionsRepository
    snapshots_repo: SnapshotsRepository
    success_repo: SuccessRepository
    run_ledger: RunLedger
    cards_epic_control_plane: Any
    callbacks: EpicRunCallbacks

    async def finalize_success(self, *, context: EpicRunContext, transcript: list[Any]) -> list[dict[str, Any]]:
        legacy_transcript = build_legacy_transcript(transcript)
        backlog = await await_infrastructure(
            "load epic backlog",
            self.cards_repo.get_by_build(context.setup.build_id),
        )
        artifacts = build_base_run_artifacts(callbacks=self.callbacks, context=context)
        session_status, failure_reason, is_workflow_terminal = await self._resolve_success_outcome(
            context=context,
            backlog=backlog,
            artifacts=artifacts,
        )
        await self._complete_success_session(
            context=context,
            session_status=session_status,
            failure_reason=failure_reason,
            backlog=backlog,
            legacy_transcript=legacy_transcript,
            is_workflow_terminal=is_workflow_terminal,
        )
        await self._record_snapshots_and_success(
            context=context,
            session_status=session_status,
            legacy_transcript=legacy_transcript,
        )
        await self._finalize_success_run(
            context=context,
            session_status=session_status,
            failure_reason=failure_reason,
            backlog=backlog,
            artifacts=artifacts,
        )
        return legacy_transcript

    async def finalize_failure(self, *, context: EpicRunContext, transcript: list[Any], exc: Exception) -> None:
        legacy_transcript = build_legacy_transcript(transcript)
        try:
            await await_infrastructure(
                "load epic backlog after failure",
                self.cards_repo.get_by_build(context.setup.build_id),
            )
        except OrketInfrastructureError:
            pass
        failed_status = validate_state_token(domain="session", state="failed")
        await await_infrastructure(
            "complete failed session",
            self.sessions_repo.complete_session(context.setup.run_id, failed_status, legacy_transcript),
        )
        log_event(
            "session_end",
            {"run_id": context.setup.run_id, "status": failed_status, "failure_class": type(exc).__name__},
            workspace=self.workspace,
        )
        artifacts = build_base_run_artifacts(callbacks=self.callbacks, context=context)
        await self._finalize_failure_run(
            context=context,
            failure=exc,
            failed_status=failed_status,
            artifacts=artifacts,
        )

    async def _resolve_success_outcome(
        self,
        *,
        context: EpicRunContext,
        backlog: list[Any],
        artifacts: dict[str, Any],
    ) -> tuple[str, str | None, bool]:
        is_workflow_terminal = all(issue.status in WORKFLOW_TERMINAL_STATUSES for issue in backlog)
        is_success_terminal = all(issue.status in SUCCESS_STATUSES for issue in backlog)
        session_status = "done" if is_success_terminal else "terminal_failure" if is_workflow_terminal else "incomplete"
        session_status = validate_state_token(domain="session", state=session_status)
        receipt_projection = await await_infrastructure(
            "materialize protocol receipts",
            self.callbacks.materialize_protocol_receipts(run_id=context.setup.run_id),
        )
        if receipt_projection:
            artifacts["protocol_receipts"] = receipt_projection
        failure_reason = await self._resolve_source_attribution_failure(context=context, session_status=session_status)
        if session_status == "done" and failure_reason is not None:
            session_status = validate_state_token(domain="session", state="terminal_failure")
        return session_status, failure_reason, is_workflow_terminal

    async def _resolve_source_attribution_failure(
        self,
        *,
        context: EpicRunContext,
        session_status: str,
    ) -> str | None:
        source_attribution_facts = await await_infrastructure(
            "collect source attribution facts",
            collect_source_attribution_facts(
                workspace=self.workspace,
                policy=context.setup.phase_c_truth_policy,
            ),
        )
        failure_reason = resolve_source_attribution_gate_failure_reason(source_attribution_facts)
        if session_status == "done" and failure_reason is not None:
            log_event(
                "source_attribution_gate_blocked",
                {
                    "run_id": context.setup.run_id,
                    "failure_reason": failure_reason,
                    "mode": source_attribution_facts.get("mode"),
                    "missing_requirements": list(source_attribution_facts.get("missing_requirements") or []),
                },
                workspace=self.workspace,
            )
        return failure_reason

    async def _complete_success_session(
        self,
        *,
        context: EpicRunContext,
        session_status: str,
        failure_reason: str | None,
        backlog: list[Any],
        legacy_transcript: list[dict[str, Any]],
        is_workflow_terminal: bool,
    ) -> None:
        await await_infrastructure(
            "complete session",
            self.sessions_repo.complete_session(context.setup.run_id, session_status, legacy_transcript),
        )
        payload = {"run_id": context.setup.run_id, "status": session_status}
        if failure_reason is not None:
            payload["failure_reason"] = failure_reason
        log_event("session_end", payload, workspace=self.workspace)
        self._log_backlog_state(
            run_id=context.setup.run_id,
            build_id=context.setup.build_id,
            session_status=session_status,
            failure_reason=failure_reason,
            backlog=backlog,
            is_workflow_terminal=is_workflow_terminal,
        )

    def _log_backlog_state(
        self,
        *,
        run_id: str,
        build_id: str,
        session_status: str,
        failure_reason: str | None,
        backlog: list[Any],
        is_workflow_terminal: bool,
    ) -> None:
        if not is_workflow_terminal:
            log_event(
                "session_incomplete",
                {
                    "run_id": run_id,
                    "build_id": build_id,
                    "open_issues": [self._issue_status_row(issue) for issue in backlog if issue.status not in WORKFLOW_TERMINAL_STATUSES],
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
                    "issues": [self._issue_status_row(issue) for issue in backlog if issue.status not in SUCCESS_STATUSES],
                    "failure_reason": failure_reason,
                },
                workspace=self.workspace,
            )

    async def _record_snapshots_and_success(
        self,
        *,
        context: EpicRunContext,
        session_status: str,
        legacy_transcript: list[dict[str, Any]],
    ) -> None:
        await await_infrastructure(
            "record snapshots",
            self.snapshots_repo.record(
                context.setup.run_id,
                {
                    "epic": context.setup.epic.model_dump(),
                    "team": context.setup.team.model_dump(),
                    "env": context.setup.env.model_dump(),
                    "build_id": context.setup.build_id,
                },
                legacy_transcript,
            ),
        )
        if session_status != "done":
            return
        await await_infrastructure(
            "record success",
            self.success_repo.record_success(
                session_id=context.setup.run_id,
                success_type="EPIC_COMPLETED",
                artifact_ref=f"build:{context.setup.build_id}",
                human_ack=None,
            ),
        )
        log_event("success_recorded", {"run_id": context.setup.run_id, "type": "EPIC_COMPLETED"}, workspace=self.workspace)

    async def _finalize_success_run(
        self,
        *,
        context: EpicRunContext,
        session_status: str,
        failure_reason: str | None,
        backlog: list[Any],
        artifacts: dict[str, Any],
    ) -> None:
        control_plane_run, control_plane_attempt = await await_infrastructure(
            "finalize epic control plane execution",
            self.cards_epic_control_plane.finalize_execution(
                run_id=context.control_plane_run.run_id,
                session_status=session_status,
                failure_reason=failure_reason,
            ),
        )
        set_control_plane_artifacts(
            artifacts,
            control_plane_run=control_plane_run,
            control_plane_attempt=control_plane_attempt,
            control_plane_step=context.control_plane_start_step,
        )
        cards_runtime_summary = self._cards_runtime_summary(backlog=backlog, session_status=session_status)
        if cards_runtime_summary:
            artifacts["cards_runtime_facts"] = cards_runtime_summary
        finalized_at = datetime.now(UTC).isoformat()
        run_summary, artifacts = await await_infrastructure(
            "materialize run summary",
            self.callbacks.materialize_run_summary(
                run_id=context.setup.run_id,
                session_status=session_status,
                failure_reason=failure_reason,
                artifacts=artifacts,
                finalized_at=finalized_at,
                phase_c_truth_policy=context.setup.phase_c_truth_policy,
            ),
        )
        gitea_export = await await_infrastructure(
            "export run artifacts",
            self.callbacks.export_run_artifacts(
                run_id=context.setup.run_id,
                run_type="epic",
                run_name=context.setup.epic.name,
                build_id=context.setup.build_id,
                session_status=session_status,
                summary=run_summary,
                failure_reason=failure_reason,
            ),
        )
        if gitea_export:
            artifacts["gitea_export"] = gitea_export
        await await_infrastructure(
            "finalize run ledger",
            self.run_ledger.finalize_run(
                session_id=context.setup.run_id,
                status=session_status,
                failure_reason=failure_reason,
                summary=run_summary,
                artifacts=artifacts,
                finalized_at=datetime.now(UTC).isoformat(),
            ),
        )

    def _cards_runtime_summary(self, *, backlog: list[Any], session_status: str) -> dict[str, Any]:
        summary = summarize_cards_runtime_issues(
            [
                {
                    "issue_id": issue.id,
                    **dict(getattr(issue, "params", {}) or {}).get("cards_runtime_summary", {}),
                }
                for issue in backlog
                if isinstance(getattr(issue, "params", None), dict)
                and isinstance(dict(issue.params).get("cards_runtime_summary"), dict)
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
        return summary

    async def _finalize_failure_run(
        self,
        *,
        context: EpicRunContext,
        failure: Exception,
        failed_status: str,
        artifacts: dict[str, Any],
    ) -> None:
        control_plane_run, control_plane_attempt = await await_infrastructure(
            "finalize failed epic control plane execution",
            self.cards_epic_control_plane.finalize_execution(
                run_id=context.control_plane_run.run_id,
                session_status=failed_status,
                failure_reason=str(failure)[:2000],
            ),
        )
        set_control_plane_artifacts(
            artifacts,
            control_plane_run=control_plane_run,
            control_plane_attempt=control_plane_attempt,
            control_plane_step=context.control_plane_start_step,
        )
        receipt_projection = await await_infrastructure(
            "materialize protocol receipts",
            self.callbacks.materialize_protocol_receipts(run_id=context.setup.run_id),
        )
        if receipt_projection:
            artifacts["protocol_receipts"] = receipt_projection
        failure_summary, artifacts = await await_infrastructure(
            "materialize failed run summary",
            self.callbacks.materialize_run_summary(
                run_id=context.setup.run_id,
                session_status=failed_status,
                failure_reason=str(failure)[:2000],
                artifacts=artifacts,
                finalized_at=datetime.now(UTC).isoformat(),
                phase_c_truth_policy=context.setup.phase_c_truth_policy,
            ),
        )
        gitea_export = await await_infrastructure(
            "export failed run artifacts",
            self.callbacks.export_run_artifacts(
                run_id=context.setup.run_id,
                run_type="epic",
                run_name=context.setup.epic.name,
                build_id=context.setup.build_id,
                session_status=failed_status,
                summary=failure_summary,
                failure_class=type(failure).__name__,
                failure_reason=str(failure)[:2000],
            ),
        )
        if gitea_export:
            artifacts["gitea_export"] = gitea_export
        await await_infrastructure(
            "finalize failed run ledger",
            self.run_ledger.finalize_run(
                session_id=context.setup.run_id,
                status=failed_status,
                failure_class=type(failure).__name__,
                failure_reason=str(failure)[:2000],
                summary=failure_summary,
                artifacts=artifacts,
                finalized_at=datetime.now(UTC).isoformat(),
            ),
        )

    @staticmethod
    def _issue_status_row(issue: Any) -> dict[str, str]:
        status = issue.status.value if hasattr(issue.status, "value") else str(issue.status)
        return {"id": issue.id, "status": status}
