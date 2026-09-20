from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

from orket.adapters.storage.async_control_plane_execution_repository import (
    AsyncControlPlaneExecutionRepository,
)
from orket.adapters.storage.async_control_plane_record_repository import (
    AsyncControlPlaneRecordRepository,
)
from orket.adapters.storage.async_governed_agent_repository import AsyncGovernedAgentRepository
from orket.adapters.storage.async_governed_agent_run_control_repository import AsyncGovernedAgentRunControlRepository
from orket.adapters.storage.control_plane_transaction import SQLiteControlPlaneTransactions
from orket.adapters.storage.governed_agent_replay_store import GovernedAgentReplayStore
from orket.application.services.governed_agent_broker_service import (
    GovernedAgentHostBroker,
    GovernedAgentModelProvider,
    GovernedAgentResolvedModelProfile,
)
from orket.application.services.governed_agent_fixture import (
    DeterministicAgentModelProvider,
    SecondIterationDeterministicVerifier,
)
from orket.application.services.governed_agent_loop_service import GovernedAgentLoopService
from orket.application.services.governed_agent_memory_service import GovernedAgentObjectiveMemory
from orket.application.services.governed_agent_model_provider import (
    PROVIDER_CHOICES as PROVIDER_CHOICES,
)
from orket.application.services.governed_agent_model_provider import (
    GovernedAgentLocalModelProvider,
    prepare_governed_agent_local_runtime,
)
from orket.application.services.governed_agent_operator_service import GovernedAgentOperatorService
from orket.core.contracts.governed_agent_ports import GovernedAgentAuthorityGuard, GovernedAgentIterationInvoker
from orket.core.contracts.governed_agent_replay import GovernedAgentReplayRepository
from orket.extensions.governed_agent_invoker import GovernedAgentSubprocessInvoker
from orket.extensions.models import GovernedAgentWorkloadLaunch
from orket_extension_sdk import AgentIterationRequest, canonical_digest_sha256


def build_governed_agent_replay_repository(db_path: str | Path) -> GovernedAgentReplayRepository:
    return GovernedAgentReplayStore(db_path)


@dataclass(slots=True)
class GovernedAgentProviderSelection:
    provider: GovernedAgentModelProvider
    profiles: dict[str, GovernedAgentResolvedModelProfile]
    proof_posture: str
    observed_path: str
    targets: dict[str, dict[str, Any]]
    _live_provider: GovernedAgentLocalModelProvider | None = None

    async def close(self) -> None:
        if self._live_provider is not None:
            await self._live_provider.close()

    def configuration_payload(self) -> dict[str, Any]:
        return {
            "proof_posture": self.proof_posture,
            "profiles": {ref: asdict(profile) for ref, profile in sorted(self.profiles.items())},
            "targets": self.targets,
        }


async def select_governed_agent_provider(
    *,
    request: AgentIterationRequest,
    launch: GovernedAgentWorkloadLaunch,
    deterministic_fixture: bool,
    model_by_role: Mapping[str, str],
    ollama_base_url: str,
    inventory_timeout_seconds: float,
    provider_name: str = "llama_cpp",
    provider_base_url: str = "",
    environment: Mapping[str, str] | None = None,
) -> GovernedAgentProviderSelection:
    requested = _validate_catalog_profiles(request, launch)
    if deterministic_fixture:
        profiles = {
            profile_ref: GovernedAgentResolvedModelProfile(
                requested_profile_ref=profile_ref,
                resolved_profile_ref=f"deterministic.{role}",
                provider="deterministic_fixture",
                provider_version="v1",
                model=f"fixture-{role}",
                model_digest="sha256:"
                + cast(str, canonical_digest_sha256({"role": role, "profile": profile_ref})),
            )
            for role, profile_ref in requested.items()
        }
        return GovernedAgentProviderSelection(
            provider=DeterministicAgentModelProvider(),
            profiles=profiles,
            proof_posture="deterministic_fixture_not_live_model",
            observed_path="primary",
            targets={},
        )
    if not model_by_role or set(model_by_role) != set(requested):
        raise ValueError("E_AGENT_LOCAL_ROLE_MODEL_MAP_MISMATCH")
    runtime = await prepare_governed_agent_local_runtime(
        request=request,
        model_by_role=model_by_role,
        provider=provider_name,
        base_url=provider_base_url or (ollama_base_url if provider_name == "ollama" else ""),
        inventory_timeout_seconds=inventory_timeout_seconds,
        environment=environment,
    )
    return GovernedAgentProviderSelection(
        provider=runtime.provider,
        profiles=runtime.profiles,
        proof_posture="live_local_model",
        observed_path="primary",
        targets={role: target.to_payload() for role, target in runtime.targets.items()},
        _live_provider=runtime.provider,
    )


def model_map_for_roles(
    request: AgentIterationRequest,
    *,
    default_model: str,
    role_overrides: Mapping[str, str],
) -> dict[str, str]:
    result = {
        profile.role: str(role_overrides.get(profile.role) or default_model).strip()
        for profile in request.model_profiles
    }
    if not all(result.values()):
        raise ValueError("E_AGENT_LOCAL_MODEL_REQUIRED")
    return result


def build_governed_agent_loop_service(
    *,
    execution: AsyncControlPlaneExecutionRepository,
    iterations: AsyncGovernedAgentRepository,
    records: AsyncControlPlaneRecordRepository,
    launch: GovernedAgentWorkloadLaunch,
    selection: GovernedAgentProviderSelection,
    authority_guard: GovernedAgentAuthorityGuard | None = None,
) -> GovernedAgentLoopService:
    if len({str(execution.db_path), str(iterations.db_path), str(records.db_path)}) != 1:
        raise ValueError("E_AGENT_CONTROL_PLANE_STORE_CONFLICT")
    broker = GovernedAgentHostBroker(
        iteration_repository=iterations,
        call_repository=iterations,
        model_provider=selection.provider,
        model_profiles=selection.profiles,
        memory_provider=GovernedAgentObjectiveMemory(iterations),
        authority_guard=authority_guard,
    )
    invoker = GovernedAgentSubprocessInvoker(
        extension_root=launch.extension_root,
        entrypoint=launch.entrypoint,
        allowed_stdlib_modules=launch.allowed_stdlib_modules,
        broker=broker,
    )
    return GovernedAgentLoopService(
        execution_repository=execution,
        iteration_repository=iterations,
        transactions=SQLiteControlPlaneTransactions(records.db_path),
        invoker=invoker,
        verifier=SecondIterationDeterministicVerifier(),
        run_controls=AsyncGovernedAgentRunControlRepository(iterations.db_path),
        authority_guard=authority_guard,
    )


def governed_agent_configuration_digest(
    launch: GovernedAgentWorkloadLaunch,
    provider: Mapping[str, Any],
) -> str:
    return "sha256:" + cast(
        str,
        canonical_digest_sha256(
            {
                "extension_id": launch.extension_id,
                "extension_version": launch.extension_version,
                "manifest_digest_sha256": launch.manifest_digest_sha256,
                "agent_declaration": launch.agent_declaration,
                "provider": dict(provider),
            }
        ),
    )


def _validate_catalog_profiles(
    request: AgentIterationRequest,
    launch: GovernedAgentWorkloadLaunch,
) -> dict[str, str]:
    declared = {
        str(item.get("role")): str(item.get("profile_ref"))
        for item in launch.agent_declaration.get("model_profiles", [])
        if isinstance(item, dict)
    }
    requested = {profile.role: str(profile.profile_ref or "") for profile in request.model_profiles}
    if requested != declared:
        raise ValueError("E_AGENT_CATALOG_MODEL_PROFILE_MISMATCH")
    return requested
def build_governed_agent_operator_service(*, db_path, iterations, invoker: GovernedAgentIterationInvoker):
    if str(iterations.db_path) != str(db_path):
        raise ValueError("E_AGENT_CONTROL_PLANE_STORE_CONFLICT")
    return GovernedAgentOperatorService(
        transactions=SQLiteControlPlaneTransactions(db_path), iteration_repository=iterations, invoker=invoker,
    )
