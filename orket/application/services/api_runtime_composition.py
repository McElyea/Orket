from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, TypeVar

from orket.adapters.storage.outward_approval_store import OutwardApprovalStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.adapters.tools.registry import DEFAULT_BUILTIN_CONNECTOR_REGISTRY
from orket.application.interactions.commit import CommitOrchestrator
from orket.application.interactions.manager import InteractionManager
from orket.application.services.api_authentication_service import ApiAuthenticationService
from orket.application.services.api_run_query_service import ApiRunQueryService
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
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.extensions import ExtensionManager
from orket.runtime_paths import resolve_control_plane_db_path
from orket.state import create_runtime_state
from orket.streaming import StreamBus, StreamBusConfig

Resource = TypeVar("Resource")


def build_api_runtime_container(
    project_root: Path,
    *,
    runtime_inputs: RuntimeInputService | None = None,
    construction_inputs: RuntimeConstructionInputs,
    own_resource: Callable[[Any], None],
) -> ApiRuntimeContainer:
    """Build the complete application-owned runtime graph for one API app."""
    root = Path(project_root).resolve()
    environment = construction_inputs.environment
    runtime_node = build_decision_node_registry(environment=environment).resolve_api_runtime()
    authentication = ApiAuthenticationService(environment)
    runtime_state = create_runtime_state()
    runtime_host = ApiRuntimeHostService(project_root=root, runtime_inputs=runtime_inputs,
        environment=environment, construction_inputs=construction_inputs)
    stream_bus = _build_stream_bus(authentication.environment)
    run_store, event_store, approval_store = _build_outward_stores(construction_inputs)
    raw_allowlist = str(environment.get("ORKET_CONNECTOR_HTTP_ALLOWLIST") or "")
    http_allowlist = tuple(host.strip().lower() for host in raw_allowlist.split(",") if host.strip())
    approval_service = OutwardApprovalService(
        approval_store=approval_store, workspace_root=root, http_allowlist=http_allowlist,
        run_store=run_store,
        event_store=event_store,
        connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
        utc_now=runtime_host.utc_now_iso,
    )
    extension_manager = ExtensionManager(project_root=root, environment=environment,
        invocation_root=construction_inputs.invocation_root)
    engine = _own(runtime_host.create_engine(runtime_node.resolve_api_workspace(root)), own_resource)
    interactions = _own(_build_interaction_manager(root, stream_bus, runtime_state, runtime_host, environment), own_resource)
    extensions = _own(ExtensionRuntimeService(project_root=root, environment=environment), own_resource)
    container = ApiRuntimeContainer(
        project_root=root,
        api_runtime_node=runtime_node,
        runtime_state=runtime_state,
        api_runtime_host=runtime_host,
        engine=engine,
        authentication=authentication,
        system_queries=ApiSystemQueryService(root, environment=authentication.environment,
                                            runtime_inputs=runtime_host.runtime_inputs),
        run_queries=ApiRunQueryService(root),
        stream_bus=stream_bus,
        interaction_manager=interactions,
        extension_manager=extension_manager,
        extension_runtime_service=extensions,
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
    governed_agent_runtime = _own(build_api_governed_agent_runtime(
        runtime_host=runtime_host,
        extension_manager=extension_manager,
        environment=environment, invocation_root=construction_inputs.invocation_root,
    ), own_resource)
    container.governed_agent_runtime = governed_agent_runtime
    container.register_owned_resource(governed_agent_runtime)
    container.register_owned_resource(container.extension_runtime_service)
    container.register_owned_resource(container.interaction_manager)
    return container


def _own(resource: Resource, register: Callable[[Any], None]) -> Resource:
    register(resource)
    return resource


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


def _build_outward_stores(inputs: RuntimeConstructionInputs) -> tuple[OutwardRunStore, OutwardRunEventStore, OutwardApprovalStore]:
    raw_path = str(inputs.environment.get("ORKET_OUTWARD_PIPELINE_DB_PATH") or "").strip()
    db_path = (inputs.invocation_root / raw_path if raw_path else resolve_control_plane_db_path(
        invocation_root=inputs.invocation_root, environment=inputs.environment))
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
