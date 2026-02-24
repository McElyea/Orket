from pathlib import Path
from typing import List, Dict, Any, Optional
import json
import os

from orket.adapters.storage.async_repositories import (
    AsyncSessionRepository, AsyncSnapshotRepository, AsyncSuccessRepository, AsyncRunLedgerRepository
)
from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.application.services.gitea_state_pilot import (
    collect_gitea_state_pilot_inputs,
    evaluate_gitea_state_pilot_readiness,
)
from orket.application.services.runtime_policy import (
    resolve_gitea_state_pilot_enabled,
    resolve_state_backend_mode,
)
from orket.application.services.kernel_v1_gateway import KernelV1Gateway
from orket.decision_nodes.registry import DecisionNodeRegistry
from orket.logging import log_event
from orket.runtime_paths import resolve_runtime_db_path
from orket.settings import load_user_settings

class OrchestrationEngine:
    """
    The Single Source of Truth for executing Orket Units.
    Encapsulates all logic previously smeared across main.py and server.py.
    """
    def __init__(self, 
                 workspace_root: Path, 
                 department: str = "core", 
                 db_path: Optional[str] = None, 
                 config_root: Optional[Path] = None,
                 cards_repo: Optional[AsyncCardRepository] = None,
                 sessions_repo: Optional[AsyncSessionRepository] = None,
                 snapshots_repo: Optional[AsyncSnapshotRepository] = None,
                 success_repo: Optional[AsyncSuccessRepository] = None,
                 run_ledger_repo: Optional[AsyncRunLedgerRepository] = None,
                 decision_nodes: Optional[DecisionNodeRegistry] = None,
                 kernel_gateway: Optional[KernelV1Gateway] = None):
        self.decision_nodes = decision_nodes or DecisionNodeRegistry()
        self.engine_runtime_node = self.decision_nodes.resolve_engine_runtime()
        self.engine_runtime_node.bootstrap_environment()
        self.workspace_root = workspace_root
        self.department = department
        self.db_path = resolve_runtime_db_path(db_path)
        self.config_root = self.engine_runtime_node.resolve_config_root(config_root)

        # Config & Assets
        from orket.orket import ConfigLoader
        self.loader = ConfigLoader(self.config_root, self.department)
        
        # Load Organization (Global Policy)
        self.org = self.loader.load_organization()
        self.state_backend_mode = self._resolve_state_backend_mode()
        self.gitea_state_pilot_enabled = self._resolve_gitea_state_pilot_enabled()
        self._validate_state_backend_mode()

        # Repositories (Accessors)
        self.cards = cards_repo or AsyncCardRepository(self.db_path)
        self.sessions = sessions_repo or AsyncSessionRepository(self.db_path)
        self.snapshots = snapshots_repo or AsyncSnapshotRepository(self.db_path)
        self.success = success_repo or AsyncSuccessRepository(self.db_path)
        self.run_ledger = run_ledger_repo or AsyncRunLedgerRepository(self.db_path)
        self.kernel_gateway = kernel_gateway or KernelV1Gateway()

        
        # PERSISTENT PIEPELINE (Avoid rebuilds)
        from orket.orket import ExecutionPipeline
        self._pipeline = ExecutionPipeline(
            self.workspace_root, 
            self.department, 
            db_path=self.db_path, 
            config_root=self.config_root,
            cards_repo=self.cards,
            sessions_repo=self.sessions,
            snapshots_repo=self.snapshots,
            success_repo=self.success,
            run_ledger_repo=self.run_ledger,
        )

    def _resolve_state_backend_mode(self) -> str:
        env_raw = (os.environ.get("ORKET_STATE_BACKEND_MODE") or "").strip()
        process_raw = ""
        if self.org and isinstance(getattr(self.org, "process_rules", None), dict):
            process_raw = str(self.org.process_rules.get("state_backend_mode", "")).strip()
        user_raw = str(load_user_settings().get("state_backend_mode", "")).strip()
        return resolve_state_backend_mode(env_raw, process_raw, user_raw)

    def _validate_state_backend_mode(self) -> None:
        if self.state_backend_mode != "gitea":
            return
        # When backend mode is explicitly forced through env, require explicit env pilot
        # enablement as well to avoid hidden host/user setting leakage.
        env_mode = (os.environ.get("ORKET_STATE_BACKEND_MODE") or "").strip().lower()
        env_pilot_raw = (os.environ.get("ORKET_ENABLE_GITEA_STATE_PILOT") or "").strip()
        if env_mode == "gitea" and not env_pilot_raw:
            raise NotImplementedError(
                "State backend mode 'gitea' requires pilot enablement "
                "(set ORKET_ENABLE_GITEA_STATE_PILOT=true or runtime policy gitea_state_pilot_enabled=true)."
            )
        if not self.gitea_state_pilot_enabled:
            raise NotImplementedError(
                "State backend mode 'gitea' requires pilot enablement "
                "(set ORKET_ENABLE_GITEA_STATE_PILOT=true or runtime policy gitea_state_pilot_enabled=true)."
            )
        readiness = evaluate_gitea_state_pilot_readiness(collect_gitea_state_pilot_inputs())
        if not bool(readiness.get("ready")):
            failures = ", ".join(list(readiness.get("failures") or [])) or "unknown readiness failure"
            raise NotImplementedError(
                f"State backend mode 'gitea' pilot readiness failed: {failures}"
            )

    def _resolve_gitea_state_pilot_enabled(self) -> bool:
        env_raw = (os.environ.get("ORKET_ENABLE_GITEA_STATE_PILOT") or "").strip()
        process_raw = ""
        if self.org and isinstance(getattr(self.org, "process_rules", None), dict):
            process_raw = str(self.org.process_rules.get("gitea_state_pilot_enabled", "")).strip()
        user_raw = str(load_user_settings().get("gitea_state_pilot_enabled", "")).strip()
        return bool(resolve_gitea_state_pilot_enabled(env_raw, process_raw, user_raw))


    async def run_card(self, card_id: str, build_id: str = None, session_id: str = None, driver_steered: bool = False, target_issue_id: str = None) -> Dict[str, Any]:
        """
        [DEPRECATED] Generic card runner. 
        Use run_epic, run_rock, or run_issue for explicit intent.
        """
        return await self._pipeline.run_card(
            card_id, 
            build_id=build_id, 
            session_id=session_id, 
            driver_steered=driver_steered, 
            target_issue_id=target_issue_id
        )

    async def run_epic(self, epic_id: str, build_id: str = None, session_id: str = None, driver_steered: bool = False) -> List[Dict]:
        """Executes a full epic orchestration."""
        return await self._pipeline.run_epic(
            epic_id,
            build_id=build_id,
            session_id=session_id,
            driver_steered=driver_steered
        )

    async def run_rock(self, rock_id: str, build_id: str = None, session_id: str = None, driver_steered: bool = False) -> Dict:
        """Executes a multi-epic rock orchestration."""
        return await self._pipeline.run_rock(
            rock_id,
            build_id=build_id,
            session_id=session_id,
            driver_steered=driver_steered
        )

    async def run_issue(self, issue_id: str, build_id: str = None, session_id: str = None, driver_steered: bool = False) -> List[Dict]:
        """Resumes or executes a single atomic issue."""
        return await self._pipeline.run_card(
            issue_id,
            build_id=build_id,
            session_id=session_id,
            driver_steered=driver_steered
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
    ) -> Dict[str, Any]:
        return await self._pipeline.run_gitea_state_loop(
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


    def get_board(self) -> Dict[str, Any]:
        from orket.board import get_board_hierarchy
        return get_board_hierarchy(self.department)

    async def get_sandboxes(self) -> List[Dict[str, Any]]:
        """Returns list of active sandboxes."""
        registry = self._pipeline.sandbox_orchestrator.registry
        return [s.model_dump() for s in registry.list_active()]

    async def stop_sandbox(self, sandbox_id: str):
        """Stops and deletes a sandbox."""
        await self._pipeline.sandbox_orchestrator.delete_sandbox(sandbox_id)

    async def halt_session(self, session_id: str):
        """Halts an active session by signaling the runtime state."""
        from orket.state import runtime_state
        task = await runtime_state.get_task(session_id)
        if task:
            task.cancel()
            log_event("session_halted", {"session_id": session_id}, self.workspace_root)

    async def archive_card(self, card_id: str, archived_by: str = "system", reason: Optional[str] = None) -> bool:
        """Archive a single card record in persistence."""
        return await self.cards.archive_card(card_id, archived_by=archived_by, reason=reason)

    async def archive_cards(
        self,
        card_ids: List[str],
        archived_by: str = "system",
        reason: Optional[str] = None,
    ) -> Dict[str, List[str]]:
        """Archive multiple cards by id."""
        return await self.cards.archive_cards(card_ids, archived_by=archived_by, reason=reason)

    async def archive_build(self, build_id: str, archived_by: str = "system", reason: Optional[str] = None) -> int:
        """Archive all cards under a build id."""
        return await self.cards.archive_build(build_id, archived_by=archived_by, reason=reason)

    async def archive_related_cards(
        self,
        related_tokens: List[str],
        archived_by: str = "system",
        reason: Optional[str] = None,
        limit: int = 500,
    ) -> Dict[str, List[str]]:
        """Archive cards whose id/build/summary/note matches any token."""
        card_ids = await self.cards.find_related_card_ids(related_tokens, limit=limit)
        return await self.cards.archive_cards(card_ids, archived_by=archived_by, reason=reason)

    def replay_turn(self, session_id: str, issue_id: str, turn_index: int, role: Optional[str] = None) -> Dict[str, Any]:
        """
        Replay diagnostics for one turn from persisted observability artifacts.
        """
        run_root = self.workspace_root / "observability" / session_id / issue_id
        if not run_root.exists():
            raise FileNotFoundError(f"No observability artifacts found for run={session_id} issue={issue_id}")

        prefix = f"{turn_index:03d}_"
        candidates = [p for p in run_root.iterdir() if p.is_dir() and p.name.startswith(prefix)]
        if role:
            role_suffix = role.lower().replace(" ", "_")
            candidates = [p for p in candidates if p.name.endswith(role_suffix)]
        if not candidates:
            raise FileNotFoundError(f"No turn artifacts found for turn_index={turn_index}")

        target = sorted(candidates)[0]
        checkpoint_path = target / "checkpoint.json"
        messages_path = target / "messages.json"
        model_path = target / "model_response.txt"
        parsed_tools_path = target / "parsed_tool_calls.json"

        def _read_json(path: Path) -> Any:
            if not path.exists():
                return None
            return json.loads(path.read_text(encoding="utf-8"))

        return {
            "turn_dir": str(target),
            "checkpoint": _read_json(checkpoint_path),
            "messages": _read_json(messages_path),
            "model_response": model_path.read_text(encoding="utf-8") if model_path.exists() else None,
            "parsed_tool_calls": _read_json(parsed_tools_path),
        }

    def kernel_start_run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return self.kernel_gateway.start_run(request)

    def kernel_execute_turn(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return self.kernel_gateway.execute_turn(request)

    def kernel_finish_run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return self.kernel_gateway.finish_run(request)

    def kernel_resolve_capability(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return self.kernel_gateway.resolve_capability(request)

    def kernel_authorize_tool_call(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return self.kernel_gateway.authorize_tool_call(request)

    def kernel_replay_run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return self.kernel_gateway.replay_run(request)

    def kernel_compare_runs(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return self.kernel_gateway.compare_runs(request)

    def kernel_run_lifecycle(
        self,
        *,
        workflow_id: str,
        execute_turn_requests: List[Dict[str, Any]],
        finish_outcome: str = "PASS",
        start_request: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self.kernel_gateway.run_lifecycle(
            workflow_id=workflow_id,
            execute_turn_requests=execute_turn_requests,
            finish_outcome=finish_outcome,
            start_request=start_request,
        )
