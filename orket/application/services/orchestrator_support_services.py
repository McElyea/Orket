from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from orket.adapters.storage.async_file_tools import AsyncFileTools


class OrchestratorSupportServices:
    """Explicitly owns orchestrator support-service construction on the live path."""

    def __init__(
        self,
        *,
        scaffolder_cls_getter: Callable[[], Any],
        dependency_manager_cls_getter: Callable[[], Any],
        deployment_planner_cls_getter: Callable[[], Any],
        runtime_verifier_cls_getter: Callable[[], Any],
        prompt_compiler_cls_getter: Callable[[], Any],
        prompt_resolver_cls_getter: Callable[[], Any],
        load_user_settings_getter: Callable[[], Callable[[], dict[str, Any]]],
    ) -> None:
        self._scaffolder_cls_getter = scaffolder_cls_getter
        self._dependency_manager_cls_getter = dependency_manager_cls_getter
        self._deployment_planner_cls_getter = deployment_planner_cls_getter
        self._runtime_verifier_cls_getter = runtime_verifier_cls_getter
        self._prompt_compiler_cls_getter = prompt_compiler_cls_getter
        self._prompt_resolver_cls_getter = prompt_resolver_cls_getter
        self._load_user_settings_getter = load_user_settings_getter

    def load_user_settings(self) -> dict[str, Any]:
        settings = self._load_user_settings_getter()()
        return settings if isinstance(settings, dict) else {}

    def create_scaffolder(
        self,
        *,
        workspace_root: Path,
        organization: Any,
        project_surface_profile: str | None,
        architecture_pattern: str | None,
    ) -> Any:
        scaffolder_cls = self._scaffolder_cls_getter()
        file_tools = AsyncFileTools(workspace_root)
        try:
            return scaffolder_cls(
                workspace_root=workspace_root,
                file_tools=file_tools,
                organization=organization,
                project_surface_profile=project_surface_profile,
                architecture_pattern=architecture_pattern,
            )
        except TypeError:
            return scaffolder_cls(
                workspace_root=workspace_root,
                file_tools=file_tools,
                organization=organization,
            )

    def create_dependency_manager(
        self,
        *,
        workspace_root: Path,
        organization: Any,
        project_surface_profile: str | None,
        architecture_pattern: str | None,
    ) -> Any:
        dependency_manager_cls = self._dependency_manager_cls_getter()
        file_tools = AsyncFileTools(workspace_root)
        try:
            return dependency_manager_cls(
                workspace_root=workspace_root,
                file_tools=file_tools,
                organization=organization,
                project_surface_profile=project_surface_profile,
                architecture_pattern=architecture_pattern,
            )
        except TypeError:
            return dependency_manager_cls(
                workspace_root=workspace_root,
                file_tools=file_tools,
                organization=organization,
            )

    def create_deployment_planner(
        self,
        *,
        workspace_root: Path,
        organization: Any,
        project_surface_profile: str | None,
        architecture_pattern: str | None,
    ) -> Any:
        deployment_planner_cls = self._deployment_planner_cls_getter()
        file_tools = AsyncFileTools(workspace_root)
        try:
            return deployment_planner_cls(
                workspace_root=workspace_root,
                file_tools=file_tools,
                organization=organization,
                project_surface_profile=project_surface_profile,
                architecture_pattern=architecture_pattern,
            )
        except TypeError:
            return deployment_planner_cls(
                workspace_root=workspace_root,
                file_tools=file_tools,
                organization=organization,
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
        runtime_verifier_cls = self._runtime_verifier_cls_getter()
        try:
            return runtime_verifier_cls(
                workspace_root,
                organization=organization,
                project_surface_profile=project_surface_profile,
                architecture_pattern=architecture_pattern,
                artifact_contract=artifact_contract,
                issue_params=issue_params,
            )
        except TypeError:
            return runtime_verifier_cls(
                workspace_root,
                organization=organization,
            )

    def resolve_prompt(self, **kwargs: Any) -> Any:
        prompt_resolver_cls = self._prompt_resolver_cls_getter()
        return prompt_resolver_cls.resolve(**kwargs)

    def compile_prompt(self, *args: Any, **kwargs: Any) -> str:
        prompt_compiler_cls = self._prompt_compiler_cls_getter()
        return str(prompt_compiler_cls.compile(*args, **kwargs))
