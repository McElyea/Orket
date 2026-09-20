from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.adapters.storage.async_repositories import (
    AsyncSessionRepository,
    AsyncSnapshotRepository,
    AsyncSuccessRepository,
)
from orket.application.services.decision_node_registry import DecisionNodeRegistry, build_decision_node_registry
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.orchestration.orchestration_config import OrchestrationConfig
from orket.runtime_paths import resolve_runtime_db_path
from orket.settings import load_user_settings

if TYPE_CHECKING:
    from orket.application.services.card_completion_service import CardCompletionService
    from orket.application.services.runtime_store_binding_service import RuntimeStoreBindingService

ConfigLoaderFactory = Callable[..., Any]
RunLedgerFactory = Callable[..., Any]
TelemetrySink = Callable[[dict[str, Any]], Any]


def normalized_user_settings(user_settings: dict[str, Any] | None = None) -> dict[str, Any]:
    if isinstance(user_settings, dict):
        return dict(user_settings)
    resolved = load_user_settings()
    return resolved if isinstance(resolved, dict) else {}


@dataclass(slots=True)
class OrketRuntimeContext:
    workspace_root: Path
    department: str
    db_path: str
    config_root: Path
    decision_nodes: DecisionNodeRegistry
    loader: Any
    org: Any
    orchestration_config: OrchestrationConfig
    user_settings: dict[str, Any]
    state_backend_mode: str
    run_ledger_mode: str
    gitea_state_pilot_enabled: bool
    cards_repo: AsyncCardRepository
    sessions_repo: AsyncSessionRepository
    snapshots_repo: AsyncSnapshotRepository
    success_repo: AsyncSuccessRepository
    run_ledger: Any
    storage_binding: RuntimeStoreBindingService
    card_completion: CardCompletionService | None = None
    construction_inputs: RuntimeConstructionInputs | None = None

    async def initialize(self) -> None:
        await self.storage_binding.initialize()
        initialize = getattr(self.run_ledger, "initialize", None)
        if callable(initialize):
            await initialize()

    async def close(self) -> None:
        for target in (
            self.run_ledger,
            self.success_repo,
            self.snapshots_repo,
            self.sessions_repo,
            self.cards_repo,
        ):
            close = getattr(target, "aclose", None) or getattr(target, "close", None)
            if not callable(close):
                continue
            maybe_awaitable = close()
            if inspect.isawaitable(maybe_awaitable):
                await maybe_awaitable

    @classmethod
    def from_env(
        cls,
        *,
        workspace_root: Path,
        department: str = "core",
        db_path: str | None = None,
        config_root: Path | None = None,
        cards_repo: AsyncCardRepository | None = None,
        card_completion: CardCompletionService | None = None,
        sessions_repo: AsyncSessionRepository | None = None,
        snapshots_repo: AsyncSnapshotRepository | None = None,
        success_repo: AsyncSuccessRepository | None = None,
        run_ledger_repo: Any = None,
        decision_nodes: DecisionNodeRegistry | None = None,
        config_loader_factory: ConfigLoaderFactory,
        config_loader_kwargs: dict[str, Any] | None = None,
        config_root_resolver: Callable[[Path | None], Path] | None = None,
        run_ledger_factory: RunLedgerFactory | None = None,
        telemetry_sink: TelemetrySink | None = None,
        primary_run_ledger_mode: str = "sqlite",
        construction_inputs: RuntimeConstructionInputs | None = None,
    ) -> OrketRuntimeContext:
        # The legacy extension package imports the engine; compose after runtime types initialize.
        from orket.application.services.card_completion_composition import build_card_completion_service
        from orket.application.services.runtime_store_binding_service import RuntimeStoreBindingService

        environment = construction_inputs.environment if construction_inputs is not None else None
        runtime_nodes = decision_nodes if decision_nodes is not None else build_decision_node_registry(environment=environment)
        resolved_workspace = Path(workspace_root).resolve()
        resolved_db_path = (resolve_runtime_db_path(db_path, invocation_root=construction_inputs.invocation_root,
            environment=environment) if construction_inputs is not None else resolve_runtime_db_path(db_path))
        selected_config_root = config_root or (construction_inputs.invocation_root if construction_inputs is not None else None)
        resolved_config_root = (
            config_root_resolver(selected_config_root)
            if config_root_resolver is not None
            else (selected_config_root or Path().resolve())
        )
        loader_options = dict(config_loader_kwargs or {})
        if construction_inputs is not None:
            loader_options.update(environment=environment, user_settings=construction_inputs.user_settings())
        loader = config_loader_factory(
            resolved_config_root,
            department,
            **loader_options,
        )
        org = loader.load_organization()
        user_settings = construction_inputs.user_settings() if construction_inputs is not None else normalized_user_settings()
        orchestration_config = OrchestrationConfig(org, environment=environment)
        state_backend_mode = orchestration_config.resolve_state_backend_mode(user_settings=user_settings)
        run_ledger_mode = orchestration_config.resolve_run_ledger_mode(user_settings=user_settings)
        gitea_state_pilot_enabled = orchestration_config.resolve_gitea_state_pilot_enabled(user_settings=user_settings)
        orchestration_config.validate_state_backend_mode(state_backend_mode, gitea_state_pilot_enabled)
        completion = card_completion or build_card_completion_service(
            db_path=resolved_db_path, workspace_root=resolved_workspace,
        )
        cards = cards_repo or AsyncCardRepository(resolved_db_path, completion_authority=completion)
        sessions = sessions_repo or AsyncSessionRepository(resolved_db_path)
        snapshots = snapshots_repo or AsyncSnapshotRepository(resolved_db_path)
        success = success_repo or AsyncSuccessRepository(resolved_db_path)
        if run_ledger_repo is not None:
            run_ledger = run_ledger_repo
        else:
            if run_ledger_factory is None or telemetry_sink is None:
                raise ValueError("run_ledger_factory and telemetry_sink are required when run_ledger_repo is not supplied.")
            run_ledger = run_ledger_factory(
                mode=run_ledger_mode,
                db_path=resolved_db_path,
                workspace_root=resolved_workspace,
                telemetry_sink=telemetry_sink,
                primary_mode=primary_run_ledger_mode,
            )
        return cls(
            workspace_root=resolved_workspace,
            department=department,
            db_path=resolved_db_path,
            config_root=resolved_config_root,
            decision_nodes=runtime_nodes,
            loader=loader,
            org=org,
            orchestration_config=orchestration_config,
            user_settings=user_settings,
            state_backend_mode=state_backend_mode,
            run_ledger_mode=run_ledger_mode,
            gitea_state_pilot_enabled=gitea_state_pilot_enabled,
            cards_repo=cards,
            sessions_repo=sessions,
            snapshots_repo=snapshots,
            success_repo=success,
            run_ledger=run_ledger,
            card_completion=completion,
            storage_binding=RuntimeStoreBindingService(resolved_db_path),
            construction_inputs=construction_inputs,
        )
