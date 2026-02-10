import asyncio
import uuid
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Type

from orket.schema import (
    CardStatus, EpicConfig, RockConfig, IssueConfig, 
    OrganizationConfig, CardType
)
from orket.infrastructure.sqlite_repositories import (
    SQLiteCardRepository, SQLiteSessionRepository, SQLiteSnapshotRepository
)
from orket.infrastructure.async_card_repository import AsyncCardRepository, CardRepositoryAdapter
from orket.logging import log_event
from orket.utils import sanitize_name

class OrchestrationEngine:
    """
    The Single Source of Truth for executing Orket Units.
    Encapsulates all logic previously smeared across main.py and server.py.
    """
    def __init__(self, workspace_root: Path, department: str = "core", db_path: str = "orket_persistence.db", config_root: Optional[Path] = None):
        self.workspace_root = workspace_root
        self.department = department
        self.db_path = db_path
        self.config_root = config_root or Path(".").resolve()
        
        # Repositories (Accessors)
        self.async_cards = AsyncCardRepository(self.db_path)
        self.cards = CardRepositoryAdapter(self.async_cards)
        
        self.sessions = SQLiteSessionRepository(self.db_path)
        self.snapshots = SQLiteSnapshotRepository(self.db_path)
        
        # Load Organization (Global Policy)
        self.org = self._load_organization()

    def _load_organization(self) -> Optional[OrganizationConfig]:
        org_path = self.config_root / "config" / "organization.json"
        if not org_path.exists():
            org_path = self.config_root / "model" / "organization.json"
            
        if org_path.exists():
            return OrganizationConfig.model_validate_json(org_path.read_text(encoding="utf-8"))
        return None

    async def run_card(self, card_id: str, build_id: str = None, session_id: str = None, driver_steered: bool = False, target_issue_id: str = None) -> Dict[str, Any]:
        """Runs a generic card by identifying its type and delegating."""
        # This will use the same logic from ExecutionPipeline but centralized
        from orket.orket import ExecutionPipeline
        pipeline = ExecutionPipeline(self.workspace_root, self.department, db_path=self.db_path, config_root=self.config_root)
        return await pipeline.run_card(card_id, build_id=build_id, session_id=session_id, driver_steered=driver_steered, target_issue_id=target_issue_id)

    def get_board(self) -> Dict[str, Any]:
        from orket.board import get_board_hierarchy
        return get_board_hierarchy(self.department)

    async def get_sandboxes(self) -> List[Dict[str, Any]]:
        """Returns list of active sandboxes."""
        from orket.orket import ExecutionPipeline
        pipeline = ExecutionPipeline(self.workspace_root, self.department, db_path=self.db_path, config_root=self.config_root)
        registry = pipeline.sandbox_orchestrator.registry
        return [s.model_dump() for s in registry.list_all()]

    async def stop_sandbox(self, sandbox_id: str):
        """Stops and deletes a sandbox."""
        from orket.orket import ExecutionPipeline
        pipeline = ExecutionPipeline(self.workspace_root, self.department, db_path=self.db_path, config_root=self.config_root)
        await pipeline.sandbox_orchestrator.delete_sandbox(sandbox_id)

    def halt_session(self, session_id: str):
        # Implementation of halt logic
        pass
