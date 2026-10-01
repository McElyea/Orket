from __future__ import annotations

from pathlib import Path
from typing import Any

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.dependency_manager import DependencyManager
from orket.application.services.deployment_planner import DeploymentPlanner
from orket.application.services.prompt_compiler import PromptCompiler
from orket.application.services.prompt_resolver import PromptResolver
from orket.application.services.runtime_verifier import RuntimeVerifier
from orket.application.services.scaffolder import Scaffolder
from orket.settings import load_user_settings


class OrchestratorSupportServices:
    """Explicitly owns orchestrator support-service construction on the live path."""

    def load_user_settings(self) -> dict[str, Any]:
        settings = load_user_settings()
        return settings if isinstance(settings, dict) else {}

    def create_scaffolder(
        self,
        *,
        workspace_root: Path,
        organization: Any,
        project_surface_profile: str | None,
        architecture_pattern: str | None,
    ) -> Any:
        file_tools = AsyncFileTools(workspace_root)
        return Scaffolder(
            workspace_root=workspace_root,
            file_tools=file_tools,
            organization=organization,
            project_surface_profile=project_surface_profile,
            architecture_pattern=architecture_pattern,
        )

    def create_dependency_manager(
        self,
        *,
        workspace_root: Path,
        organization: Any,
        project_surface_profile: str | None,
        architecture_pattern: str | None,
    ) -> Any:
        file_tools = AsyncFileTools(workspace_root)
        return DependencyManager(
            workspace_root=workspace_root,
            file_tools=file_tools,
            organization=organization,
            project_surface_profile=project_surface_profile,
            architecture_pattern=architecture_pattern,
        )

    def create_deployment_planner(
        self,
        *,
        workspace_root: Path,
        organization: Any,
        project_surface_profile: str | None,
        architecture_pattern: str | None,
    ) -> Any:
        file_tools = AsyncFileTools(workspace_root)
        return DeploymentPlanner(
            workspace_root=workspace_root,
            file_tools=file_tools,
            organization=organization,
            project_surface_profile=project_surface_profile,
            architecture_pattern=architecture_pattern,
        )

    def create_runtime_verifier(
        self,
        *,
        workspace_root: Path,
        organization: Any,
        project_surface_profile: str | None,
        architecture_pattern: str | None,
        artifact_contract: dict[str, Any],
        issue_params: dict[str, Any],
    ) -> Any:
        return RuntimeVerifier(
            workspace_root,
            organization=organization,
            project_surface_profile=project_surface_profile,
            architecture_pattern=architecture_pattern,
            artifact_contract=artifact_contract,
            issue_params=issue_params,
        )

    def resolve_prompt(self, **kwargs: Any) -> Any:
        return PromptResolver.resolve(**kwargs)

    def compile_prompt(self, *args: Any, **kwargs: Any) -> str:
        return str(PromptCompiler.compile(*args, **kwargs))
