from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from orket.adapters.storage.outward_approval_store import OutwardApprovalStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.adapters.tools.registry import DEFAULT_BUILTIN_CONNECTOR_REGISTRY
from orket.application.interactions.commit import CommitOrchestrator
from orket.application.interactions.manager import InteractionManager
from orket.application.services.api_authentication_service import ApiAuthenticationService
from orket.application.services.api_runtime_container import ApiRuntimeContainer
from orket.application.services.api_runtime_host_service import ApiRuntimeHostService
from orket.application.services.api_system_query_service import ApiSystemQueryService
from orket.application.services.decision_node_registry import build_decision_node_registry
from orket.application.services.extension_runtime_service import ExtensionRuntimeService
from orket.application.services.governed_agent_api_composition import (
    build_api_governed_agent_runtime,
)
from orket.application.services.model_selection_service import ModelSelectionService
from orket.application.services.outward_approval_service import OutwardApprovalService
from orket.application.services.outward_ledger_service import OutwardLedgerService
from orket.application.services.outward_run_execution_service import OutwardRunExecutionService
from orket.application.services.outward_run_inspection_service import OutwardRunInspectionService
from orket.application.services.outward_run_service import OutwardRunService
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.extensions import ExtensionManager
from orket.runtime_paths import resolve_control_plane_db_path
from orket.state import create_runtime_state
from orket.streaming import StreamBus, StreamBusConfig


def build_api_runtime_container(
    project_root: Path,
    *,
    runtime_inputs: RuntimeInputService | None = None,
    environment: Mapping[str, str] | None = None,
) -> ApiRuntimeContainer:
    """Build the complete application-owned runtime graph for one API app."""
    root = Path(project_root).resolve()
    runtime_node = build_decision_node_registry(environment=environment).resolve_api_runtime()
    authentication = ApiAuthenticationService(os.environ if environment is None else environment)
    runtime_state = create_runtime_state()
    runtime_host = ApiRuntimeHostService(project_root=root, runtime_inputs=runtime_inputs, environment=authentication.environment)
    stream_bus = _build_stream_bus(authentication.environment)
    run_store, event_store, approval_store = _build_outward_stores()
    raw_allowlist = str(os.getenv("ORKET_CONNECTOR_HTTP_ALLOWLIST") or "")
    http_allowlist = tuple(host.strip().lower() for host in raw_allowlist.split(",") if host.strip())
    approval_service = OutwardApprovalService(
        approval_store=approval_store, workspace_root=root, http_allowlist=http_allowlist,
        run_store=run_store,
        event_store=event_store,
        connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
        utc_now=runtime_host.utc_now_iso,
    )
    extension_manager = ExtensionManager(project_root=root)
    container = ApiRuntimeContainer(
        project_root=root,
        api_runtime_node=runtime_node,
        runtime_state=runtime_state,
        api_runtime_host=runtime_host,
        engine=runtime_host.create_engine(runtime_node.resolve_api_workspace(root)),
        authentication=authentication,
        system_queries=ApiSystemQueryService(root, environment=authentication.environment,
                                            runtime_inputs=runtime_host.runtime_inputs),
        stream_bus=stream_bus,
        interaction_manager=_build_interaction_manager(root, stream_bus, runtime_state, runtime_host,
                                                       authentication.environment),
        extension_manager=extension_manager,
        extension_runtime_service=ExtensionRuntimeService(project_root=root, environment=authentication.environment),
        outward_run_store=run_store,
        outward_run_event_store=event_store,
        outward_approval_store=approval_store,
        outward_run_service=OutwardRunService(
            run_store=run_store,
            event_store=event_store,
            run_id_factory=runtime_host.create_session_id,
            utc_now=runtime_host.utc_now_iso,
            unit_of_work=approval_service.unit_of_work,
        ),
        outward_approval_service=approval_service,
        outward_run_execution_service=_build_outward_execution_service(
            root, runtime_host, run_store, event_store, approval_service
        ),
        outward_run_inspection_service=OutwardRunInspectionService(run_store=run_store, event_store=event_store,
                                                                 unit_of_work=approval_service.unit_of_work),
        outward_ledger_service=OutwardLedgerService(
            run_store=run_store,
            event_store=event_store,
            utc_now=runtime_host.utc_now_iso,
        ),
        model_selection=ModelSelectionService(environment=authentication.environment),
    )
    governed_agent_runtime = build_api_governed_agent_runtime(
        runtime_host=runtime_host,
        extension_manager=extension_manager,
    )
    container.governed_agent_runtime = governed_agent_runtime
    container.register_owned_resource(governed_agent_runtime)
    container.register_owned_resource(container.extension_runtime_service)
    container.register_owned_resource(container.interaction_manager)
    return container


def _build_stream_bus(environment: Mapping[str, str]) -> StreamBus:
    return StreamBus(
        StreamBusConfig(
            best_effort_max_events_per_turn=int(environment.get("ORKET_STREAM_BEST_EFFORT_MAX_EVENTS_PER_TURN", "256")),
            best_effort_max_events_per_turn_override=int(
                environment.get("ORKET_STREAM_BEST_EFFORT_MAX_EVENTS_PER_TURN_OVERRIDE", "2048")
            ),
            bounded_max_events_per_turn=int(environment.get("ORKET_STREAM_BOUNDED_MAX_EVENTS_PER_TURN", "128")),
            max_bytes_per_turn_queue=int(environment.get("ORKET_STREAM_MAX_BYTES_PER_TURN_QUEUE", "1000000")),
        )
    )


def _build_interaction_manager(root: Path, bus: StreamBus, state: object, host: ApiRuntimeHostService,
                               environment: Mapping[str, str]) -> InteractionManager:
    async def register_session(session_id: str) -> None:
        await state.register_interaction_session(session_id)  # type: ignore[attr-defined]

    async def unregister_session(session_id: str) -> None:
        await state.unregister_interaction_session(session_id)  # type: ignore[attr-defined]

    return InteractionManager(
        bus=bus,
        commit_orchestrator=CommitOrchestrator(project_root=root),
        project_root=root,
        inputs=host.runtime_inputs,
        stream_enabled=str(environment.get("ORKET_STREAM_EVENTS_V1", "false")).strip().lower() in {"1", "true", "yes", "on"},
        on_session_started=register_session,
        on_session_closed=unregister_session,
    )


def _build_outward_stores() -> tuple[OutwardRunStore, OutwardRunEventStore, OutwardApprovalStore]:
    raw_path = str(os.getenv("ORKET_OUTWARD_PIPELINE_DB_PATH") or "").strip()
    db_path = Path(raw_path) if raw_path else resolve_control_plane_db_path()
    return OutwardRunStore(db_path), OutwardRunEventStore(db_path), OutwardApprovalStore(db_path)


def _build_outward_execution_service(
    root: Path,
    runtime_host: ApiRuntimeHostService,
    run_store: OutwardRunStore,
    event_store: OutwardRunEventStore,
    approval_service: OutwardApprovalService,
) -> OutwardRunExecutionService:
    return OutwardRunExecutionService(
        run_store=run_store,
        event_store=event_store,
        approval_service=approval_service,
        connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
        workspace_root=root,
        utc_now=runtime_host.utc_now_iso,
        connector_service=approval_service.connectors,
        effect_owner_id_factory=runtime_host.runtime_inputs.create_effect_owner_id,
    )
