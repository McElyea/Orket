from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from orket.exceptions import CardNotFound
from orket.logging import log_event
from orket.schema import CardStatus, EpicConfig, IssueConfig, RockConfig
from orket.utils import sanitize_name


class ExecutionPipelineResumeMixin:
    if TYPE_CHECKING:
        loader: Any
        runtime_inputs: Any
        execution_runtime_node: Any
        workspace: Path
        pipeline_wiring_service: Any
        bug_fix_manager: Any
        async_cards: Any
        orchestrator: Any

    async def _run_epic_collection_entry(
        self,
        collection_name: str,
        build_id: str | None = None,
        session_id: str | None = None,
        driver_steered: bool = False,
        model_override: str | None = None,
    ) -> dict[str, Any]:
        collection = await self.loader.load_asset_async("rocks", collection_name, RockConfig)
        requested_session_id = session_id or self.runtime_inputs.create_session_id()
        sid = self.execution_runtime_node.select_epic_collection_session_id(requested_session_id)
        active_build = self.execution_runtime_node.select_epic_collection_build_id(
            build_id, collection_name, sanitize_name
        )
        results = []
        for entry in collection.epics:
            epic_ws = self.workspace / entry["epic"]
            sub_pipeline = self.pipeline_wiring_service.create_sub_pipeline(
                parent_pipeline=self,
                epic_workspace=epic_ws,
                department=entry["department"],
            )
            res = await sub_pipeline.run_card(
                entry["epic"],
                build_id=active_build,
                session_id=sid,
                driver_steered=driver_steered,
                model_override=model_override,
            )
            results.append({"epic": entry["epic"], "transcript": res})

        log_event(
            "epic_collection_phase_transition",
            {"collection": collection.name, "phase": "bug_fix"},
            workspace=self.workspace,
        )
        await self.bug_fix_manager.start_phase(collection.id)

        return {"collection": collection.name, "results": results}

    async def _find_parent_epic(self, issue_id: str) -> tuple[EpicConfig | None, str | None, IssueConfig | None]:
        for ename in await self.loader.list_assets_async("epics"):
            try:
                epic = await self.loader.load_asset_async("epics", ename, EpicConfig)
                for issue in epic.issues:
                    if issue.id == issue_id:
                        return epic, ename, issue
            except (FileNotFoundError, ValueError, CardNotFound):
                continue
        return None, None, None

    async def _resume_target_issue_if_existing(
        self,
        *,
        issues: list[Any],
        target_issue_id: str,
        run_id: str,
        active_build: str,
    ) -> None:
        target_issue = next(
            (issue for issue in issues if str(getattr(issue, "id", "")).strip() == str(target_issue_id).strip()),
            None,
        )
        if target_issue is None:
            return
        current_status = getattr(target_issue, "status", None)
        current_status_value = getattr(current_status, "value", current_status)
        current_status_token = str(current_status_value or "").strip() or "unknown"
        try:
            normalized_status = CardStatus(current_status_token.lower())
        except ValueError:
            normalized_status = None
        if normalized_status in {
            CardStatus.READY,
            CardStatus.IN_PROGRESS,
            CardStatus.CODE_REVIEW,
            CardStatus.AWAITING_GUARD_REVIEW,
        }:
            log_event(
                "resume_target_issue_preserved",
                {
                    "run_id": run_id,
                    "build_id": active_build,
                    "issue_id": str(getattr(target_issue, "id", "")).strip(),
                    "current_status": current_status_token,
                },
                workspace=self.workspace,
            )
            return
        metadata = {
            "run_id": run_id,
            "build_id": active_build,
            "target_issue_id": str(target_issue_id).strip(),
            "previous_status": current_status_token,
        }
        await self.async_cards.update_status(
            str(getattr(target_issue, "id", "")).strip(),
            CardStatus.READY,
            reason="resume_target_issue",
            metadata=metadata,
        )
        target_issue.status = CardStatus.READY
        await self._publish_resume_transition_control_plane(
            issue=target_issue,
            current_status=current_status,
            target_status=CardStatus.READY,
            run_id=run_id,
            reason="resume_target_issue",
            metadata=metadata,
        )
        log_event(
            "resume_target_issue_requeued",
            {
                "run_id": run_id,
                "build_id": active_build,
                "issue_id": str(getattr(target_issue, "id", "")).strip(),
                "previous_status": current_status_token,
                "new_status": CardStatus.READY.value,
            },
            workspace=self.workspace,
        )

    async def _resume_stalled_issues(
        self,
        issues: list[Any],
        run_id: str,
        active_build: str,
        *,
        preserve_issue_ids: set[str] | None = None,
    ) -> None:
        stalled_states = {CardStatus.IN_PROGRESS, CardStatus.CODE_REVIEW, CardStatus.AWAITING_GUARD_REVIEW}
        preserved_ids = {str(issue_id).strip() for issue_id in (preserve_issue_ids or set()) if str(issue_id).strip()}
        for issue in issues:
            issue_id = str(getattr(issue, "id", "")).strip()
            if issue_id in preserved_ids:
                continue
            if issue.status in stalled_states:
                current_status = issue.status
                current_status_token = str(
                    current_status.value if hasattr(current_status, "value") else current_status
                ).strip() or "unknown"
                metadata = {
                    "run_id": run_id,
                    "build_id": active_build,
                    "previous_status": current_status_token,
                }
                await self.async_cards.update_status(
                    issue_id,
                    CardStatus.READY,
                    reason="resume_requeue",
                    metadata=metadata,
                )
                issue.status = CardStatus.READY
                await self._publish_resume_transition_control_plane(
                    issue=issue,
                    current_status=current_status,
                    target_status=CardStatus.READY,
                    run_id=run_id,
                    reason="resume_requeue",
                    metadata=metadata,
                )
                log_event(
                    "resume_requeue_issue",
                    {
                        "run_id": run_id,
                        "build_id": active_build,
                        "issue_id": issue_id,
                        "previous_status": current_status_token,
                        "new_status": CardStatus.READY.value,
                    },
                    workspace=self.workspace,
                )

    async def _publish_resume_transition_control_plane(
        self,
        *,
        issue: Any,
        current_status: CardStatus | str | None,
        target_status: CardStatus,
        run_id: str,
        reason: str,
        metadata: dict[str, Any],
    ) -> None:
        issue_id = str(getattr(issue, "id", "")).strip()
        if not issue_id or not str(run_id or "").strip():
            return
        assignee = getattr(issue, "assignee", None)
        normalized_reason = str(reason or "").strip().lower()
        issue_control_plane = getattr(self.orchestrator, "issue_control_plane", None)
        handled_by_dispatch = False
        if issue_control_plane is not None:
            handled_by_dispatch = await issue_control_plane.publish_issue_transition(
                session_id=run_id,
                issue_id=issue_id,
                current_status=current_status or "unknown",
                target_status=target_status,
                reason=normalized_reason,
                assignee=assignee,
                turn_index=metadata.get("turn_index"),
                review_turn=bool(metadata.get("review_turn", False)),
            )
        scheduler_control_plane = getattr(self.orchestrator, "scheduler_control_plane", None)
        if scheduler_control_plane is None or handled_by_dispatch or normalized_reason == "turn_dispatch":
            return
        await scheduler_control_plane.publish_scheduler_transition(
            session_id=run_id,
            issue_id=issue_id,
            current_status=current_status or "unknown",
            target_status=target_status,
            reason=normalized_reason,
            assignee=assignee,
            metadata=dict(metadata),
        )

    async def verify_issue(self, issue_id: str) -> Any:
        return await self.orchestrator.verify_issue(issue_id)
