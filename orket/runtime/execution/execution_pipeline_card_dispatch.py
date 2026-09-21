from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from orket.core.contracts.runtime_execution_result import RuntimeCollectionResult, RuntimeExecutionResult
from orket.exceptions import CardNotFound
from orket.logging import log_event
from orket.runtime.gitea_state_loop import GiteaStateLoopRunner
from orket.runtime.settings import resolve_str


class ExecutionPipelineCardDispatchMixin:
    if TYPE_CHECKING:
        loader: Any
        workspace: Path
        state_backend_mode: str
        org: Any

        async def initialize(self) -> None: ...

        async def _find_parent_epic(self, issue_id: str) -> tuple[Any, str | None, Any]: ...

        async def _run_epic_collection_entry(
            self,
            collection_name: str,
            build_id: str | None = None,
            session_id: str | None = None,
            driver_steered: bool = False,
            model_override: str | None = None,
        ) -> RuntimeCollectionResult: ...

        def _build_epic_run_orchestrator(self) -> Any: ...

    async def run_card(
        self,
        card_id: str,
        *,
        build_id: str | None = None,
        session_id: str | None = None,
        driver_steered: bool = False,
        target_issue_id: str | None = None,
        model_override: str | None = None,
        admission_recovery: dict[str, Any] | None = None,
        export_recovery: dict[str, Any] | None = None, approval_recovery: dict[str, Any] | None = None,
    ) -> RuntimeExecutionResult | RuntimeCollectionResult:
        """Canonical public runtime dispatcher over normalized card facts."""
        await self.initialize()
        target_kind, parent_epic_name = await self._resolve_run_card_target(card_id)
        if admission_recovery is not None and target_kind != "epic":
            raise ValueError("E_EPIC_ADMISSION_RECOVERY_EPIC_REQUIRED")
        if export_recovery is not None and target_kind != "epic":
            raise ValueError("E_EPIC_EXPORT_RECOVERY_EPIC_REQUIRED")
        if approval_recovery is not None and target_kind != "epic":
            raise ValueError("E_EPIC_APPROVAL_RECOVERY_EPIC_REQUIRED")
        if target_kind == "epic":
            return await self._run_epic_entry(
                card_id,
                build_id=build_id,
                session_id=session_id,
                driver_steered=driver_steered,
                target_issue_id=target_issue_id,
                model_override=model_override,
                admission_recovery=admission_recovery, export_recovery=export_recovery, approval_recovery=approval_recovery,
            )
        if target_kind == "epic_collection":
            return await self._run_epic_collection_entry(
                card_id,
                build_id=build_id,
                session_id=session_id,
                driver_steered=driver_steered,
                model_override=model_override,
            )
        return await self._run_issue_entry(
            card_id,
            build_id=build_id,
            session_id=session_id,
            driver_steered=driver_steered,
            parent_epic_name=parent_epic_name,
            target_issue_id=target_issue_id,
            model_override=model_override,
        )

    async def _resolve_run_card_target(self, card_id: str) -> tuple[str, str | None]:
        """Resolve one normalized runtime target kind from explicit asset facts."""
        epics = await self.loader.list_assets_async("epics")
        if card_id in epics:
            return "epic", None

        rocks = await self.loader.list_assets_async("rocks")
        if card_id in rocks:
            return "epic_collection", None

        parent_epic, parent_ename, _ = await self._find_parent_epic(card_id)
        if parent_epic and parent_ename:
            return "issue", parent_ename

        raise CardNotFound(f"Card {card_id} not found.")

    async def run_issue(
        self,
        issue_id: str,
        build_id: str | None = None,
        session_id: str | None = None,
        driver_steered: bool = False,
        model_override: str | None = None,
    ) -> RuntimeExecutionResult | RuntimeCollectionResult:
        """Compatibility wrapper over the canonical run_card surface."""
        return await self.run_card(
            issue_id,
            build_id=build_id,
            session_id=session_id,
            driver_steered=driver_steered,
            model_override=model_override,
        )

    async def run_rock(
        self,
        rock_name: str,
        build_id: str | None = None,
        session_id: str | None = None,
        driver_steered: bool = False,
        model_override: str | None = None,
    ) -> RuntimeExecutionResult | RuntimeCollectionResult:
        """Legacy compatibility wrapper over the canonical run_card surface."""
        return await self.run_card(
            rock_name,
            build_id=build_id,
            session_id=session_id,
            driver_steered=driver_steered,
            model_override=model_override,
        )

    async def _run_issue_entry(
        self,
        issue_id: str,
        build_id: str | None = None,
        session_id: str | None = None,
        driver_steered: bool = False,
        parent_epic_name: str | None = None,
        target_issue_id: str | None = None,
        model_override: str | None = None,
    ) -> RuntimeExecutionResult | RuntimeCollectionResult:
        parent_ename = parent_epic_name
        if parent_ename is None:
            parent_epic, parent_ename, _ = await self._find_parent_epic(issue_id)
            if not parent_epic or parent_ename is None:
                raise CardNotFound(f"Card {issue_id} not found.")
        log_event(
            "pipeline_atomic_issue",
            {"card_id": issue_id, "parent_epic": parent_ename},
            workspace=self.workspace,
        )
        del target_issue_id
        return await self._run_epic_entry(
            parent_ename,
            build_id=build_id,
            session_id=session_id,
            driver_steered=driver_steered,
            target_issue_id=issue_id,
            model_override=model_override,
        )

    async def run_gitea_state_loop(
        self,
        *,
        worker_id: str,
        fetch_limit: int = 5,
        lease_seconds: int = 30,
        renew_interval_seconds: float = 5.0,
        max_iterations: int | None = None,
        max_idle_streak: int | None = None,
        max_duration_seconds: float | None = None,
        idle_sleep_seconds: float = 0.0,
        summary_out: str | Path | None = None,
    ) -> dict[str, Any]:
        runner = GiteaStateLoopRunner(
            state_backend_mode=self.state_backend_mode,
            organization=getattr(self, "org", None),
            run_card=self.run_card,
            runtime_inputs=self.runtime_inputs,
            construction_inputs=self.runtime_context.construction_inputs,
            control_plane_db_path=Path(self.orchestrator.control_plane_execution_repository.db_path),
        )
        await self.initialize()
        return await runner.run(
            worker_id=worker_id,
            fetch_limit=fetch_limit,
            lease_seconds=lease_seconds,
            renew_interval_seconds=renew_interval_seconds,
            max_iterations=max_iterations,
            max_idle_streak=max_idle_streak,
            max_duration_seconds=max_duration_seconds,
            idle_sleep_seconds=idle_sleep_seconds,
            summary_out=summary_out,
        )

    def _resolve_idesign_mode(self) -> str:
        raw = resolve_str(
            "ORKET_IDESIGN_MODE",
            process_rules=getattr(self.org, "process_rules", None),
            process_key="idesign_mode",
        )
        normalized = raw.lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "force_idesign": "force_idesign",
            "force_i_design": "force_idesign",
            "force_none": "force_none",
            "force_nothing": "force_none",
            "none": "force_none",
            "architect_decides": "architect_decides",
            "architect_decide": "architect_decides",
            "let_architect_decide": "architect_decides",
        }
        return aliases.get(normalized, "force_none")

    async def run_epic(
        self,
        epic_name: str,
        build_id: str | None = None,
        session_id: str | None = None,
        driver_steered: bool = False,
        target_issue_id: str | None = None,
        model_override: str | None = None,
    ) -> RuntimeExecutionResult | RuntimeCollectionResult:
        """Compatibility wrapper over the canonical run_card surface."""
        result = await self.run_card(
            epic_name,
            build_id=build_id,
            session_id=session_id,
            driver_steered=driver_steered,
            target_issue_id=target_issue_id,
            model_override=model_override,
        )
        return result

    async def _run_epic_entry(
        self,
        epic_name: str,
        build_id: str | None = None,
        session_id: str | None = None,
        driver_steered: bool = False,
        target_issue_id: str | None = None,
        model_override: str | None = None,
        admission_recovery: dict[str, Any] | None = None,
        export_recovery: dict[str, Any] | None = None, approval_recovery: dict[str, Any] | None = None,
    ) -> RuntimeExecutionResult | RuntimeCollectionResult:
        result = await self._build_epic_run_orchestrator().run(
            epic_name,
            build_id=build_id,
            session_id=session_id,
            driver_steered=driver_steered,
            target_issue_id=target_issue_id,
            model_override=str(model_override or "").strip(),
            admission_recovery=admission_recovery, export_recovery=export_recovery, approval_recovery=approval_recovery,
        )
        return result
