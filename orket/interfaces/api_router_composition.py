"""Ordered transport binding over the existing API application context."""
from __future__ import annotations

from functools import partial

from orket.application.services.runtime_policy import (
    resolve_frontend_framework_mode,
    resolve_gitea_state_pilot_enabled,
    resolve_local_prompting_allow_fallback,
    resolve_local_prompting_fallback_profile_id,
    resolve_local_prompting_mode,
    resolve_project_surface_profile,
    resolve_protocol_env_allowlist_setting,
    resolve_protocol_locale_setting,
    resolve_protocol_network_allowlist_setting,
    resolve_protocol_network_mode_setting,
    resolve_protocol_timezone_setting,
    resolve_run_ledger_mode,
    resolve_small_project_builder_variant,
    resolve_state_backend_mode,
)
from orket.interfaces.api_invocation import invoke_api_method, schedule_api_invocation_task
from orket.interfaces.api_settings import (
    SETTINGS_ORDER,
    SETTINGS_SCHEMA,
    parse_setting_value,
    resolve_settings_snapshot,
)
from orket.interfaces.routers.card_authoring import build_card_authoring_router
from orket.interfaces.routers.cards import build_cards_router
from orket.interfaces.routers.extension_runtime import build_extension_runtime_router
from orket.interfaces.routers.flows import build_flows_router
from orket.interfaces.routers.governed_agents import build_governed_agents_router
from orket.interfaces.routers.kernel import build_kernel_router
from orket.interfaces.routers.logs import build_logs_router
from orket.interfaces.routers.outward_inspection import build_outward_inspection_router
from orket.interfaces.routers.outward_ledger import build_outward_ledger_router
from orket.interfaces.routers.outward_runs import build_outward_runs_router
from orket.interfaces.routers.run_history import build_run_history_router
from orket.interfaces.routers.runs import build_runs_router
from orket.interfaces.routers.sandboxes import build_sandboxes_router
from orket.interfaces.routers.session_history import build_session_history_router
from orket.interfaces.routers.sessions import build_sessions_router
from orket.interfaces.routers.settings import build_settings_router
from orket.interfaces.routers.system import build_system_router


def _build_policy_settings_router(*, observe, load, save, process_rules, error):
    return build_settings_router(
        settings_order=SETTINGS_ORDER, settings_schema=SETTINGS_SCHEMA,
        observe_runtime_policy=observe, load_user_settings=load, save_user_settings=save,
        runtime_policy_process_rules=process_rules, settings_validation_error=error,
        resolve_settings_snapshot=resolve_settings_snapshot, parse_setting_value=parse_setting_value,
        resolve_frontend_framework_mode=resolve_frontend_framework_mode,
        resolve_project_surface_profile=resolve_project_surface_profile,
        resolve_small_project_builder_variant=resolve_small_project_builder_variant,
        resolve_state_backend_mode=resolve_state_backend_mode,
        resolve_run_ledger_mode=resolve_run_ledger_mode,
        resolve_protocol_timezone_setting=resolve_protocol_timezone_setting,
        resolve_protocol_locale_setting=resolve_protocol_locale_setting,
        resolve_protocol_network_mode_setting=resolve_protocol_network_mode_setting,
        resolve_protocol_network_allowlist_setting=resolve_protocol_network_allowlist_setting,
        resolve_protocol_env_allowlist_setting=resolve_protocol_env_allowlist_setting,
        resolve_local_prompting_mode=resolve_local_prompting_mode,
        resolve_local_prompting_allow_fallback=resolve_local_prompting_allow_fallback,
        resolve_local_prompting_fallback_profile_id=resolve_local_prompting_fallback_profile_id,
        resolve_gitea_state_pilot_enabled=resolve_gitea_state_pilot_enabled,
    )


def register_api_domain_routes(
    router, *, runtime_getter, project_root_getter, runtime_node_getter, engine_getter, governed_runtime_getter,
    outbound_filter, observe_policy, runtime_policy_process_rules, load_user_settings, save_user_settings,
    settings_validation_error,
):
    schedule = partial(schedule_api_invocation_task, runtime_getter=runtime_getter)
    router.include_router(build_kernel_router(engine_getter,
        outward_approval_service_getter=lambda: runtime_getter().outward_approval_service,
        outward_execution_service_getter=lambda: runtime_getter().outward_run_execution_service,
        outbound_filter=outbound_filter))
    router.include_router(build_cards_router(engine_getter, runtime_node_getter))
    router.include_router(build_card_authoring_router(engine_getter, project_root_getter))
    router.include_router(build_flows_router(engine_getter=engine_getter,
        host_getter=lambda: runtime_getter().api_runtime_host, schedule_async_invocation_task=schedule))
    router.include_router(build_runs_router(engine_getter,
        outward_execution_service_getter=lambda: runtime_getter().outward_run_execution_service,
        outbound_filter=outbound_filter))
    router.include_router(build_outward_ledger_router(service_getter=lambda: runtime_getter().outward_ledger_service,
        outbound_filter=outbound_filter))
    router.include_router(_build_policy_settings_router(observe=observe_policy, load=load_user_settings,
        save=save_user_settings, process_rules=runtime_policy_process_rules, error=settings_validation_error))
    router.include_router(build_system_router(project_root_getter=project_root_getter,
        runtime_state=lambda: runtime_getter().runtime_state, api_runtime_node_getter=runtime_node_getter,
        system_queries_getter=lambda: runtime_getter().system_queries,
        runtime_host_getter=lambda: runtime_getter().api_runtime_host,
        now_local=lambda: runtime_getter().system_queries.local_now(), events_getter=lambda: runtime_getter().events,
        model_selection_getter=lambda: runtime_getter().model_selection,
        invoke_async_method=invoke_api_method, schedule_async_invocation_task=schedule, engine_getter=engine_getter))
    router.include_router(build_sessions_router(turn_service_getter=lambda: runtime_getter().interactions(),
        workspace_root_getter=project_root_getter, cancellation_service_getter=lambda: runtime_getter().interaction_cancellation()))
    router.include_router(build_extension_runtime_router(service_getter=lambda: runtime_getter().extension_runtime_service))
    router.include_router(build_governed_agents_router(runtime_getter=governed_runtime_getter, outbound_filter=outbound_filter))
    router.include_router(build_outward_runs_router(runtime_getter=runtime_getter, outbound_filter=outbound_filter))
    router.include_router(build_outward_inspection_router(run_service_getter=lambda: runtime_getter().outward_run_service,
        inspection_service_getter=lambda: runtime_getter().outward_run_inspection_service, outbound_filter=outbound_filter))
    router.include_router(build_run_history_router(runtime_getter=runtime_getter, outbound_filter=outbound_filter))
    router.include_router(build_session_history_router(runtime_getter=runtime_getter))
    router.include_router(build_sandboxes_router(runtime_getter=runtime_getter))
    router.include_router(build_logs_router(runtime_getter=runtime_getter))
