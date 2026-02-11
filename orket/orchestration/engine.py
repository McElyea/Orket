from pathlib import Path
from typing import List, Dict, Any, Optional

from orket.infrastructure.async_repositories import (
    AsyncSessionRepository, AsyncSnapshotRepository, AsyncSuccessRepository
)
from orket.infrastructure.async_card_repository import AsyncCardRepository
from orket.decision_nodes.registry import DecisionNodeRegistry
from orket.logging import log_event

class OrchestrationEngine:
    """
    The Single Source of Truth for executing Orket Units.
    Encapsulates all logic previously smeared across main.py and server.py.
    """
    def __init__(self, 
                 workspace_root: Path, 
                 department: str = "core", 
                 db_path: str = "orket_persistence.db", 
                 config_root: Optional[Path] = None,
                 cards_repo: Optional[AsyncCardRepository] = None,
                 sessions_repo: Optional[AsyncSessionRepository] = None,
                 snapshots_repo: Optional[AsyncSnapshotRepository] = None,
                 success_repo: Optional[AsyncSuccessRepository] = None,
                 decision_nodes: Optional[DecisionNodeRegistry] = None):
        self.decision_nodes = decision_nodes or DecisionNodeRegistry()
        self.engine_runtime_node = self.decision_nodes.resolve_engine_runtime()
        self.engine_runtime_node.bootstrap_environment()
        self.workspace_root = workspace_root
        self.department = department
        self.db_path = db_path
        self.config_root = self.engine_runtime_node.resolve_config_root(config_root)
        
        # Repositories (Accessors)
        self.cards = cards_repo or AsyncCardRepository(self.db_path)
        self.sessions = sessions_repo or AsyncSessionRepository(self.db_path)
        self.snapshots = snapshots_repo or AsyncSnapshotRepository(self.db_path)
        self.success = success_repo or AsyncSuccessRepository(self.db_path)
        
        # Config & Assets
        from orket.orket import ConfigLoader
        self.loader = ConfigLoader(self.config_root, self.department)
        
        # Load Organization (Global Policy)
        self.org = self.loader.load_organization()

        
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
            success_repo=self.success
        )


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


    def get_board(self) -> Dict[str, Any]:
        from orket.board import get_board_hierarchy
        return get_board_hierarchy(self.department)

    async def get_sandboxes(self) -> List[Dict[str, Any]]:
        """Returns list of active sandboxes."""
        registry = self._pipeline.sandbox_orchestrator.registry
        return [s.model_dump() for s in registry.list_all()]

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
