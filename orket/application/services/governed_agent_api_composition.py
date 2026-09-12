from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import cast

from orket.adapters.storage.async_control_plane_execution_repository import (
    AsyncControlPlaneExecutionRepository,
)
from orket.adapters.storage.async_control_plane_record_repository import (
    AsyncControlPlaneRecordRepository,
)
from orket.adapters.storage.async_governed_agent_repository import AsyncGovernedAgentRepository
from orket.adapters.storage.async_governed_agent_run_control_repository import AsyncGovernedAgentRunControlRepository
from orket.adapters.storage.async_governed_agent_schedule_repository import (
    AsyncGovernedAgentScheduleRepository,
)
from orket.adapters.storage.async_governed_agent_wake_control_repository import (
    AsyncGovernedAgentWakeControlRepository,
)
from orket.adapters.storage.async_governed_agent_wake_repository import (
    AsyncGovernedAgentWakeRepository,
)
from orket.adapters.storage.async_governed_agent_webhook_repository import (
    AsyncGovernedAgentWebhookRepository,
)
from orket.adapters.storage.async_repositories import AsyncPendingGateRepository
from orket.adapters.tools.governed_agent_file_effect_executor import GovernedAgentFileEffectExecutor
from orket.application.services.api_runtime_host_service import ApiRuntimeHostService
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.governed_agent_effect_control_service import GovernedAgentEffectControlService
from orket.application.services.governed_agent_effect_resume_service import GovernedAgentEffectResumeService
from orket.application.services.governed_agent_effect_service import GovernedAgentEffectService
from orket.application.services.governed_agent_inspection_service import GovernedAgentInspectionService
from orket.application.services.governed_agent_run_control_service import GovernedAgentRunControlService
from orket.application.services.governed_agent_runtime import GovernedAgentRuntime
from orket.application.services.governed_agent_scheduled_wake_service import (
    GovernedAgentScheduledWakeService,
)
from orket.application.services.governed_agent_supervisor import GovernedAgentSupervisor
from orket.application.services.governed_agent_wake_dispatcher import (
    PROVIDER_CHOICES,
    GovernedAgentProviderConfiguration,
    GovernedAgentWakeLoopDispatcher,
    ProviderMode,
)
from orket.application.services.governed_agent_webhook_ingress_service import (
    GovernedAgentWebhookIngressService,
)
from orket.extensions import ExtensionManager
from orket.runtime.config.defaults import configured_provider
from orket.runtime_paths import resolve_control_plane_db_path


@dataclass(frozen=True, slots=True)
class GovernedAgentApiSettings:
    supervisor_enabled: bool
    db_path: Path
    provider_mode: str
    default_model: str
    role_models: dict[str, str]
    ollama_base_url: str
    provider_base_url: str
    inventory_timeout_seconds: float
    capacity_limit: int
    lease_seconds: float
    renewal_interval_seconds: float
    idle_wait_seconds: float
    webhook_issuer_ref: str | None
    webhook_key_id: str | None
    webhook_secret: str | None = field(repr=False)
    webhook_replay_window_seconds: int


def build_api_governed_agent_runtime(
    *,
    runtime_host: ApiRuntimeHostService,
    extension_manager: ExtensionManager,
) -> GovernedAgentRuntime:
    settings = _settings()
    execution = AsyncControlPlaneExecutionRepository(settings.db_path)
    iterations = AsyncGovernedAgentRepository(settings.db_path)
    wakes = AsyncGovernedAgentWakeRepository(settings.db_path)
    schedules = AsyncGovernedAgentScheduleRepository(settings.db_path)
    webhooks = AsyncGovernedAgentWebhookRepository(settings.db_path)
    wake_controls = AsyncGovernedAgentWakeControlRepository(settings.db_path)
    records = AsyncControlPlaneRecordRepository(settings.db_path)
    pending = AsyncPendingGateRepository(settings.db_path)
    publication = ControlPlanePublicationService(repository=records)
    effects, effect_resumes = _effect_services(
        settings=settings,
        extension_manager=extension_manager,
        execution=execution,
        iterations=iterations,
        publication=publication,
        pending=pending,
    )
    provider = _provider_configuration(settings)
    dispatcher = GovernedAgentWakeLoopDispatcher(
        execution_repository=execution,
        iteration_repository=iterations,
        record_repository=records,
        extension_manager=extension_manager,
        provider=provider,
        effect_service=effects,
        effect_resume_service=effect_resumes,
    )
    supervisor = _supervisor(settings, runtime_host, wakes, dispatcher)
    scheduled_wakes = _scheduled_wakes(schedules, supervisor)
    webhook_ingress = _webhook_ingress(settings, runtime_host, webhooks, supervisor)
    effect_controls = GovernedAgentEffectControlService(
        execution_repository=execution,
        iteration_repository=iterations,
        publication=publication,
        effects=effects,
        resumes=effect_resumes,
        wakes=wakes,
        notify_ready=supervisor.notify,
    )
    inspector = GovernedAgentInspectionService(
        execution_repository=execution,
        iteration_repository=iterations,
        call_repository=iterations,
        truth_repository=records,
        wake_repository=wakes,
        record_repository=records,
        pending_gate_repository=pending,
        wake_control_repository=wake_controls,
        schedule_repository=schedules,
        webhook_repository=webhooks,
    )
    return GovernedAgentRuntime(
        wake_repository=wakes,
        wake_control_repository=wake_controls,
        scheduled_wakes=scheduled_wakes,
        webhook_ingress=webhook_ingress,
        effect_controls=effect_controls,
        run_controls=GovernedAgentRunControlService(AsyncGovernedAgentRunControlRepository(settings.db_path)),
        inspector=inspector,
        supervisor=supervisor,
        supervisor_enabled=settings.supervisor_enabled,
        now_utc=runtime_host.utc_now_iso,
        provider_mode=settings.provider_mode,
        capacity_limit=settings.capacity_limit,
    )


def _effect_services(
    *,
    settings: GovernedAgentApiSettings,
    extension_manager: ExtensionManager,
    execution: AsyncControlPlaneExecutionRepository,
    iterations: AsyncGovernedAgentRepository,
    publication: ControlPlanePublicationService,
    pending: AsyncPendingGateRepository,
) -> tuple[GovernedAgentEffectService, GovernedAgentEffectResumeService]:
    effects = GovernedAgentEffectService(
        execution_repository=execution,
        publication=publication,
        pending_gates=pending,
        file_executor=GovernedAgentFileEffectExecutor(extension_manager.project_root),
    )
    resumes = GovernedAgentEffectResumeService(
        execution_repository=execution,
        iteration_repository=iterations,
        publication=publication,
    )
    return effects, resumes


def _scheduled_wakes(
    schedules: AsyncGovernedAgentScheduleRepository,
    supervisor: GovernedAgentSupervisor,
) -> GovernedAgentScheduledWakeService:
    return GovernedAgentScheduledWakeService(
        repository=schedules,
        notify_ready=supervisor.notify,
    )


def _provider_configuration(settings: GovernedAgentApiSettings) -> GovernedAgentProviderConfiguration:
    return GovernedAgentProviderConfiguration(
        mode=cast(ProviderMode, settings.provider_mode),
        default_model=settings.default_model,
        role_models=settings.role_models,
        ollama_base_url=settings.ollama_base_url,
        provider_base_url=settings.provider_base_url,
        inventory_timeout_seconds=settings.inventory_timeout_seconds,
        capacity_limit=settings.capacity_limit,
    )


def _supervisor(
    settings: GovernedAgentApiSettings,
    runtime_host: ApiRuntimeHostService,
    wakes: AsyncGovernedAgentWakeRepository,
    dispatcher: GovernedAgentWakeLoopDispatcher,
) -> GovernedAgentSupervisor:
    return GovernedAgentSupervisor(
        repository=wakes,
        dispatcher=dispatcher,
        owner_id=f"api-agent-supervisor:{runtime_host.create_session_id()}",
        max_active_claims=settings.capacity_limit,
        now_utc=runtime_host.utc_now_iso,
        lease_expires_at_utc=lambda now: _lease_expiry(now, settings.lease_seconds),
        idle_wait_seconds=settings.idle_wait_seconds,
        renewal_interval_seconds=settings.renewal_interval_seconds,
    )


def _webhook_ingress(
    settings: GovernedAgentApiSettings,
    runtime_host: ApiRuntimeHostService,
    webhooks: AsyncGovernedAgentWebhookRepository,
    supervisor: GovernedAgentSupervisor,
) -> GovernedAgentWebhookIngressService:
    return GovernedAgentWebhookIngressService(
        repository=webhooks,
        now_utc=runtime_host.utc_now_iso,
        issuer_ref=settings.webhook_issuer_ref,
        key_id=settings.webhook_key_id,
        secret=settings.webhook_secret,
        replay_window_seconds=settings.webhook_replay_window_seconds,
        notify_ready=supervisor.notify,
    )


def _settings() -> GovernedAgentApiSettings:
    raw_db = str(os.getenv("ORKET_GOVERNED_AGENT_DB_PATH") or "").strip()
    role_models = {
        role: str(os.getenv(f"ORKET_GOVERNED_AGENT_{role.upper()}_MODEL") or "").strip()
        for role in ("planner", "actor", "critic")
        if str(os.getenv(f"ORKET_GOVERNED_AGENT_{role.upper()}_MODEL") or "").strip()
    }
    settings = GovernedAgentApiSettings(
        supervisor_enabled=_env_bool("ORKET_GOVERNED_AGENT_SUPERVISOR_ENABLED", False),
        db_path=Path(raw_db).resolve() if raw_db else resolve_control_plane_db_path(),
        provider_mode=configured_provider("ORKET_GOVERNED_AGENT_PROVIDER"),
        default_model=_configured_model(),
        role_models=role_models,
        ollama_base_url=str(os.getenv("ORKET_GOVERNED_AGENT_OLLAMA_BASE_URL") or "").strip(),
        provider_base_url=str(os.getenv("ORKET_GOVERNED_AGENT_BASE_URL") or "").strip(),
        inventory_timeout_seconds=_env_float("ORKET_GOVERNED_AGENT_INVENTORY_TIMEOUT_SECONDS", 30.0),
        capacity_limit=_env_int("ORKET_GOVERNED_AGENT_CAPACITY_LIMIT", 1),
        lease_seconds=_env_float("ORKET_GOVERNED_AGENT_CLAIM_LEASE_SECONDS", 120.0),
        renewal_interval_seconds=_env_float("ORKET_GOVERNED_AGENT_CLAIM_RENEWAL_SECONDS", 30.0),
        idle_wait_seconds=_env_float("ORKET_GOVERNED_AGENT_IDLE_WAIT_SECONDS", 1.0),
        webhook_issuer_ref=_env_optional("ORKET_GOVERNED_AGENT_WEBHOOK_ISSUER_REF"),
        webhook_key_id=_env_optional("ORKET_GOVERNED_AGENT_WEBHOOK_KEY_ID"),
        webhook_secret=_env_optional("ORKET_GOVERNED_AGENT_WEBHOOK_SECRET"),
        webhook_replay_window_seconds=_env_int("ORKET_GOVERNED_AGENT_WEBHOOK_REPLAY_WINDOW_SECONDS", 300),
    )
    if settings.provider_mode != "deterministic_fixture" and settings.provider_mode not in PROVIDER_CHOICES:
        raise ValueError("E_AGENT_PROVIDER_MODE_INVALID")
    if (
        settings.supervisor_enabled
        and settings.provider_mode != "deterministic_fixture"
        and not settings.default_model
        and set(settings.role_models) != {"planner", "actor", "critic"}
    ):
        raise ValueError("E_AGENT_LOCAL_MODEL_REQUIRED")
    if (
        settings.capacity_limit < 1
        or settings.lease_seconds <= 0
        or settings.renewal_interval_seconds <= 0
        or settings.renewal_interval_seconds >= settings.lease_seconds
        or settings.idle_wait_seconds <= 0
    ):
        raise ValueError("E_AGENT_API_RUNTIME_CONFIGURATION_INVALID")
    webhook_values = (
        settings.webhook_issuer_ref,
        settings.webhook_key_id,
        settings.webhook_secret,
    )
    if any(webhook_values) and not all(webhook_values):
        raise ValueError("E_AGENT_WEBHOOK_CONFIGURATION_INCOMPLETE")
    if not 1 <= settings.webhook_replay_window_seconds <= 3600:
        raise ValueError("E_AGENT_WEBHOOK_REPLAY_WINDOW_INVALID")
    return settings


def _lease_expiry(now_utc: str, lease_seconds: float) -> str:
    try:
        now = datetime.fromisoformat(now_utc.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("E_AGENT_API_RUNTIME_CLOCK_INVALID") from exc
    if now.tzinfo is None:
        raise ValueError("E_AGENT_API_RUNTIME_CLOCK_INVALID")
    return (now + timedelta(seconds=lease_seconds)).isoformat()


def _env_bool(name: str, default: bool) -> bool:
    raw = str(os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"E_AGENT_API_RUNTIME_BOOLEAN_INVALID:{name}")


def _env_float(name: str, default: float) -> float:
    try:
        return float(str(os.getenv(name) or default))
    except ValueError as exc:
        raise ValueError(f"E_AGENT_API_RUNTIME_NUMBER_INVALID:{name}") from exc


def _env_int(name: str, default: int) -> int:
    try:
        return int(str(os.getenv(name) or default))
    except ValueError as exc:
        raise ValueError(f"E_AGENT_API_RUNTIME_NUMBER_INVALID:{name}") from exc


def _env_optional(name: str) -> str | None:
    value = str(os.getenv(name) or "").strip()
    return value or None


def _configured_model() -> str:
    provider = str(os.getenv("ORKET_GOVERNED_AGENT_PROVIDER") or "").strip().lower()
    selected = str(os.getenv("ORKET_GOVERNED_AGENT_MODEL") or "").strip()
    if selected:
        return selected
    if provider == "ollama":
        return str(os.getenv("ORKET_GOVERNED_AGENT_OLLAMA_MODEL") or "").strip()
    return ""
