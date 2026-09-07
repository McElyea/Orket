from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, cast

from orket.adapters.llm.governed_agent_ollama_provider import (
    GovernedAgentOllamaModelProvider,
    prepare_governed_agent_ollama_runtime,
)
from orket.application.services.governed_agent_broker_service import (
    GovernedAgentModelProvider,
    GovernedAgentResolvedModelProfile,
)
from orket.application.services.governed_agent_fixture import DeterministicAgentModelProvider
from orket.extensions.models import GovernedAgentWorkloadLaunch
from orket_extension_sdk import AgentIterationRequest, canonical_digest_sha256


@dataclass(slots=True)
class GovernedAgentProviderSelection:
    provider: GovernedAgentModelProvider
    profiles: dict[str, GovernedAgentResolvedModelProfile]
    proof_posture: str
    observed_path: str
    targets: dict[str, dict[str, Any]]
    _live_provider: GovernedAgentOllamaModelProvider | None = None

    async def close(self) -> None:
        if self._live_provider is not None:
            await self._live_provider.close()

    def configuration_payload(self) -> dict[str, Any]:
        return {
            "proof_posture": self.proof_posture,
            "profiles": {
                ref: asdict(profile)
                for ref, profile in sorted(self.profiles.items())
            },
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
        raise ValueError("E_AGENT_OLLAMA_ROLE_MODEL_MAP_MISMATCH")
    runtime = await prepare_governed_agent_ollama_runtime(
        request=request,
        model_by_role=model_by_role,
        base_url=ollama_base_url,
        inventory_timeout_seconds=inventory_timeout_seconds,
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
        raise ValueError("E_AGENT_OLLAMA_MODEL_REQUIRED")
    return result


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
