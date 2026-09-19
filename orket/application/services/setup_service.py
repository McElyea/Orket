"""Admit explicit setup choices and retain all initialization effects through interruption."""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.setup_project_store import SetupProjectStore
from orket.application.services.user_settings_service import SettingsLocation, UserSettingsService
from orket.runtime.registry.module_registry import ModuleResolutionError, modules_for_profile
from orket.schema import ArchitecturePrescription, BrandingConfig, OrganizationConfig


@dataclass(frozen=True)
class SetupService:
    root: Path
    settings_location: SettingsLocation

    def __post_init__(self):
        if not self.root.is_absolute() or not self.settings_location.invocation_root.is_absolute():
            raise ValueError("E_SETUP_ROOT_ABSOLUTE_REQUIRED")

    async def initialize(self, choices: dict[str, str]) -> dict[str, str]:
        captured = deepcopy(choices)
        profile = captured["module_profile"].strip().lower()
        try:
            modules_for_profile(profile)
        except ModuleResolutionError as exc:
            raise ValueError(str(exc)) from exc
        config = OrganizationConfig(name=captured["name"], vision=captured["vision"], ethos=captured["ethos"],
            branding=BrandingConfig(), architecture=ArchitecturePrescription(idesign_threshold=7), departments=["core"])
        organization = config.model_dump_json(indent=4).encode("utf-8")
        return await run_owned_thread(lambda: self._initialize(captured, profile, organization), label="project-setup")

    def _initialize(self, choices: dict[str, str], profile: str, organization: bytes) -> dict[str, str]:
        store = SetupProjectStore(self.root)
        settings = UserSettingsService(self.settings_location)
        with store.guard():
            result = store.publish(organization, workspace=choices["workspace"], model=choices["model"])
            # Shared settings authority preserves unrelated keys under its own native guard.
            # Organization, directories and settings are separate verified effects, not a transaction.
            settings.update("module_profile", profile)
            return {**result, "module_profile": profile}
