from __future__ import annotations

import asyncio
from collections import defaultdict
from pathlib import Path
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


_THIS_MODULE_NAME = __name__

_PATCHABLE_NAMES = (
    "Scaffolder",
    "ScaffoldValidationError",
    "DependencyManager",
    "DependencyValidationError",
    "DeploymentPlanner",
    "DeploymentValidationError",
    "RuntimeVerifier",
    "PromptCompiler",
    "PromptResolver",
    "load_user_settings",
    "load_user_preferences",
)


def _sync_patchable_symbols() -> None:
    """Keep ops-layer globals aligned with orchestrator module monkeypatches."""
    import sys

    this_mod = sys.modules[_THIS_MODULE_NAME]
    for name in _PATCHABLE_NAMES:
        setattr(orchestrator_ops, name, getattr(this_mod, name))


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

    def _resolve_architecture_mode(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._resolve_architecture_mode(self, *args, **kwargs)

    def _resolve_frontend_framework_mode(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._resolve_frontend_framework_mode(self, *args, **kwargs)

    def _resolve_architecture_pattern(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._resolve_architecture_pattern(self, *args, **kwargs)

    def _resolve_project_surface_profile(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._resolve_project_surface_profile(self, *args, **kwargs)

    def _resolve_small_project_builder_variant(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._resolve_small_project_builder_variant(self, *args, **kwargs)

    def _resolve_protocol_governed_enabled(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._resolve_protocol_governed_enabled(self, *args, **kwargs)

    def _resolve_protocol_max_response_bytes(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._resolve_protocol_max_response_bytes(self, *args, **kwargs)

    def _resolve_protocol_max_tool_calls(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._resolve_protocol_max_tool_calls(self, *args, **kwargs)

    def _resolve_protocol_determinism_context(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._resolve_protocol_determinism_context(self, *args, **kwargs)

    def _resolve_local_prompting_mode(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._resolve_local_prompting_mode(self, *args, **kwargs)

    def _resolve_local_prompting_allow_fallback(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._resolve_local_prompting_allow_fallback(self, *args, **kwargs)

    def _resolve_local_prompting_fallback_profile_id(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._resolve_local_prompting_fallback_profile_id(self, *args, **kwargs)

    def _resolve_workflow_profile(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._resolve_workflow_profile(self, *args, **kwargs)

    async def _request_issue_transition(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return await orchestrator_ops._request_issue_transition(self, *args, **kwargs)

    def _small_project_issue_threshold(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._small_project_issue_threshold(self, *args, **kwargs)

    def _should_auto_inject_small_project_reviewer(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._should_auto_inject_small_project_reviewer(self, *args, **kwargs)

    def _small_project_reviewer_seat_name(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._small_project_reviewer_seat_name(self, *args, **kwargs)

    def _auto_inject_small_project_reviewer_seat(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._auto_inject_small_project_reviewer_seat(self, *args, **kwargs)

    def _resolve_small_project_team_policy(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._resolve_small_project_team_policy(self, *args, **kwargs)

    def _resolve_bool_flag(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._resolve_bool_flag(self, *args, **kwargs)

    def _is_sandbox_disabled(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._is_sandbox_disabled(self, *args, **kwargs)

    def _is_scaffolder_disabled(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._is_scaffolder_disabled(self, *args, **kwargs)

    def _is_dependency_manager_disabled(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._is_dependency_manager_disabled(self, *args, **kwargs)

    def _is_runtime_verifier_disabled(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._is_runtime_verifier_disabled(self, *args, **kwargs)

    def _is_deployment_planner_disabled(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._is_deployment_planner_disabled(self, *args, **kwargs)

    def _resolve_prompt_resolver_mode(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._resolve_prompt_resolver_mode(self, *args, **kwargs)

    def _resolve_prompt_selection_policy(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._resolve_prompt_selection_policy(self, *args, **kwargs)

    def _resolve_prompt_selection_strict(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._resolve_prompt_selection_strict(self, *args, **kwargs)

    def _resolve_prompt_version_exact(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._resolve_prompt_version_exact(self, *args, **kwargs)

    def _resolve_verification_scope_limits(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._resolve_verification_scope_limits(self, *args, **kwargs)

    def _history_context(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._history_context(self, *args, **kwargs)

    async def _propagate_dependency_blocks(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return await orchestrator_ops._propagate_dependency_blocks(self, *args, **kwargs)

    async def _maybe_schedule_team_replan(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return await orchestrator_ops._maybe_schedule_team_replan(self, *args, **kwargs)

    async def _execute_issue_turn(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return await orchestrator_ops._execute_issue_turn(self, *args, **kwargs)

    def _validate_guard_rejection_payload(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._validate_guard_rejection_payload(self, *args, **kwargs)

    async def _create_pending_gate_request(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return await orchestrator_ops._create_pending_gate_request(self, *args, **kwargs)

    async def _create_pending_tool_approval_request(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return await orchestrator_ops._create_pending_tool_approval_request(self, *args, **kwargs)

    def _build_turn_context(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._build_turn_context(self, *args, **kwargs)

    async def _build_dependency_context(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return await orchestrator_ops._build_dependency_context(self, *args, **kwargs)

    def _extract_guard_review_payload(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._extract_guard_review_payload(self, *args, **kwargs)

    def _resolve_guard_event(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._resolve_guard_event(self, *args, **kwargs)

    async def _dispatch_turn(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return await orchestrator_ops._dispatch_turn(self, *args, **kwargs)

    async def _handle_failure(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return await orchestrator_ops._handle_failure(self, *args, **kwargs)

    def _is_issue_idesign_enabled(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._is_issue_idesign_enabled(self, *args, **kwargs)

    def _normalize_governance_violation_message(self, *args: Any, **kwargs: Any) -> Any:
        _sync_patchable_symbols()
        return orchestrator_ops._normalize_governance_violation_message(self, *args, **kwargs)

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
