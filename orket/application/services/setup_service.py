"""Admit explicit setup choices and retain all initialization effects through interruption."""
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.project_environment_store import publish_project_environment
from orket.adapters.storage.setup_project_store import SetupProjectStore
from orket.application.services.user_settings_service import SettingsLocation, UserSettingsService
from orket.core.contracts.provider_runtime import DEFAULT_LOCAL_MODEL, PROVIDER_CHOICES, provider_from_environment
from orket.core.contracts.provider_setup import ProviderSetup, validate_provider_endpoint
from orket.runtime.config.provider_runtime_target import default_base_url
from orket.runtime.registry.module_registry import ModuleResolutionError, modules_for_profile
from orket.schema import ArchitecturePrescription, BrandingConfig, OrganizationConfig


def provider_choices() -> tuple[str, ...]:
    return PROVIDER_CHOICES


def provider_setup_defaults(environment: Mapping[str, str], *, provider: str = "") -> dict[str, str]:
    selected = provider or provider_from_environment(environment)
    endpoint = validate_provider_endpoint(default_base_url(selected, environment=environment))
    return {"provider": selected, "model": DEFAULT_LOCAL_MODEL, "base_url": endpoint}


@dataclass(frozen=True)
class SetupService:
    root: Path
    settings_location: SettingsLocation

    def __post_init__(self):
        if not self.root.is_absolute() or not self.settings_location.invocation_root.is_absolute():
            raise ValueError("E_SETUP_ROOT_ABSOLUTE_REQUIRED")

    async def initialize(self, choices: dict[str, str], *, provider: ProviderSetup | None = None) -> dict[str, str]:
        captured = deepcopy(choices)
        profile = captured["module_profile"].strip().lower()
        try:
            modules_for_profile(profile)
        except ModuleResolutionError as exc:
            raise ValueError(str(exc)) from exc
        config = OrganizationConfig(name=captured["name"], vision=captured["vision"], ethos=captured["ethos"],
            branding=BrandingConfig(), architecture=ArchitecturePrescription(idesign_threshold=7), departments=["core"])
        environment_values = provider.environment_values() if provider is not None else None
        if provider is not None:
            config.process_rules["default_llm"] = provider.model
        organization = config.model_dump_json(indent=4).encode("utf-8")
        return await run_owned_thread(lambda: self._initialize(captured, profile, organization, environment_values),
                                      label="project-setup")

    def _initialize(self, choices: dict[str, str], profile: str, organization: bytes,
                    environment_values: dict[str, str] | None = None) -> dict[str, str]:
        store = SetupProjectStore(self.root)
        settings = UserSettingsService(self.settings_location)
        with store.guard():
            result = store.publish(organization, workspace=choices["workspace"], model=choices["model"])
            # Shared settings authority preserves unrelated keys under its own native guard.
            # Organization, directories and settings are separate verified effects, not a transaction.
            settings.update("module_profile", profile)
            if environment_values is not None:
                result["environment"] = publish_project_environment(self.root, environment_values)
            return {**result, "module_profile": profile}
