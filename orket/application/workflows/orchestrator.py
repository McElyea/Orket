from __future__ import annotations

import asyncio
from collections import defaultdict
from pathlib import Path
from types import MethodType
from typing import Any

from orket.adapters.storage.async_repositories import AsyncPendingGateRepository
from orket.core.contracts.repositories import CardRepository, SnapshotRepository
from orket.decision_nodes.registry import DecisionNodeRegistry
from orket.orchestration.notes import NoteStore
from orket.schema import CardStatus, EnvironmentConfig, EpicConfig, IssueConfig, TeamConfig

from . import orchestrator_ops

# Compatibility re-exports used by tests and monkeypatch hooks.
Scaffolder = orchestrator_ops.Scaffolder
ScaffoldValidationError = orchestrator_ops.ScaffoldValidationError
DependencyManager = orchestrator_ops.DependencyManager
DependencyValidationError = orchestrator_ops.DependencyValidationError
DeploymentPlanner = orchestrator_ops.DeploymentPlanner
DeploymentValidationError = orchestrator_ops.DeploymentValidationError
RuntimeVerifier = orchestrator_ops.RuntimeVerifier
PromptCompiler = orchestrator_ops.PromptCompiler
PromptResolver = orchestrator_ops.PromptResolver
load_user_settings = orchestrator_ops.load_user_settings
load_user_preferences = orchestrator_ops.load_user_preferences


def _sync_patchable_symbols() -> None:
    """Keep ops-layer globals aligned with orchestrator module monkeypatches."""
    orchestrator_ops.Scaffolder = Scaffolder
    orchestrator_ops.ScaffoldValidationError = ScaffoldValidationError
    orchestrator_ops.DependencyManager = DependencyManager
    orchestrator_ops.DependencyValidationError = DependencyValidationError
    orchestrator_ops.DeploymentPlanner = DeploymentPlanner
    orchestrator_ops.DeploymentValidationError = DeploymentValidationError
    orchestrator_ops.RuntimeVerifier = RuntimeVerifier
    orchestrator_ops.PromptCompiler = PromptCompiler
    orchestrator_ops.PromptResolver = PromptResolver
    orchestrator_ops.load_user_settings = load_user_settings
    orchestrator_ops.load_user_preferences = load_user_preferences


class Orchestrator:
    """Thin coordinator; operational methods are delegated to orchestrator_ops."""

    def __init__(
        self,
        workspace: Path,
        async_cards: CardRepository,
        snapshots: SnapshotRepository,
        org: Any,
        config_root: Path,
        db_path: str,
        loader: Any,
        sandbox_orchestrator: Any,
    ):
        self.workspace = workspace
        self.async_cards = async_cards
        self.snapshots = snapshots
        self.org = org
        self.config_root = config_root
        self.db_path = db_path
        self.loader = loader
        self.sandbox_orchestrator = sandbox_orchestrator

        from orket.services.memory_store import MemoryStore

        memory_db = Path(db_path).parent / "project_memory.db"
        self.memory = MemoryStore(memory_db)

        self.notes = NoteStore()
        self.transcript = []
        self._sandbox_locks = defaultdict(asyncio.Lock)
        self._sandbox_failed_rocks = set()
        self._team_replan_counts = defaultdict(int)
        self.pending_gates = AsyncPendingGateRepository(self.db_path)
        self.decision_nodes = DecisionNodeRegistry()
        self.planner_node = self.decision_nodes.resolve_planner(self.org)
        self.router_node = self.decision_nodes.resolve_router(self.org)
        self.evaluator_node = self.decision_nodes.resolve_evaluator(self.org)
        self.loop_policy_node = self.decision_nodes.resolve_orchestration_loop(self.org)
        self.context_window = self.loop_policy_node.context_window(self.org)
        self.model_client_node = self.decision_nodes.resolve_model_client(self.org)

    def __getattr__(self, name: str) -> Any:
        _sync_patchable_symbols()
        target = getattr(orchestrator_ops, name, None)
        if callable(target):
            return MethodType(target, self)
        raise AttributeError(name)

    async def verify_issue(self, issue_id: str, run_id: str | None = None) -> Any:
        _sync_patchable_symbols()
        return await orchestrator_ops.verify_issue(self, issue_id, run_id)

    async def _trigger_sandbox(self, epic: EpicConfig, run_id: str | None = None):
        _sync_patchable_symbols()
        return await orchestrator_ops._trigger_sandbox(self, epic, run_id)

    async def execute_epic(
        self,
        *,
        active_build: str,
        run_id: str,
        epic: EpicConfig,
        team: TeamConfig,
        env: EnvironmentConfig,
        target_issue_id: str | None = None,
        resume_mode: bool = False,
    ) -> list[IssueConfig]:
        _sync_patchable_symbols()
        return await orchestrator_ops.execute_epic(
            self,
            active_build=active_build,
            run_id=run_id,
            epic=epic,
            team=team,
            env=env,
            target_issue_id=target_issue_id,
            resume_mode=resume_mode,
        )

    async def _save_checkpoint(
        self,
        run_id: str,
        epic: EpicConfig,
        team: TeamConfig,
        env: EnvironmentConfig,
        active_build: str,
    ):
        _sync_patchable_symbols()
        return await orchestrator_ops._save_checkpoint(self, run_id, epic, team, env, active_build)


__all__ = ["Orchestrator", "CardStatus"]
