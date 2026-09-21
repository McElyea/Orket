from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Coroutine, Mapping
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel, ValidationError

from orket.adapters.execution.owned_io import require_sync_context, run_owned_thread
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.decision_node_registry import DecisionNodeRegistry, build_decision_node_registry
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.application.services.schema_input_service import validate_config_asset_json
from orket.exceptions import CardNotFound
from orket.logging import log_event

if TYPE_CHECKING:
    from orket.schema import DepartmentConfig, OrganizationConfig

T = TypeVar("T")


class ConfigLoader:
    """
    Unified Configuration and Asset Loader.
    Priority: 1. config/ (Unified) 2. model/{dept}/ (Legacy) 3. model/core/ (Fallback)
    """

    def __init__(
        self,
        root: Path,
        department: str = "core",
        organization: Any | None = None,
        decision_nodes: DecisionNodeRegistry | None = None,
        environment: Mapping[str, str] | None = None,
        user_settings: dict[str, Any] | None = None,
        runtime_inputs: RuntimeInputService | None = None,
    ) -> None:
        self.runtime_inputs = RuntimeInputService() if runtime_inputs is None else runtime_inputs
        self.root = root
        self.config_dir = root / "config"
        self.model_dir = root / "model"
        self.department = department
        self.organization = organization
        self._environment = dict(environment) if environment is not None else None
        self._user_settings = json.dumps(user_settings, allow_nan=False) if user_settings is not None else None
        self.decision_nodes = decision_nodes or build_decision_node_registry(environment=self._environment)
        self.loader_strategy_node = self.decision_nodes.resolve_loader_strategy(self.organization)
        self.file_tools = AsyncFileTools(self.root)

    def _run_async(self, coro: Coroutine[Any, Any, T]) -> T:
        """Permit synchronous bootstrap only; loop callers use the async methods."""
        try:
            require_sync_context(code="E_CONFIG_LOADER_REQUIRES_ASYNC_METHOD")
        except RuntimeError:
            coro.close()
            raise
        return asyncio.run(coro)

    def _relative_path_for_read(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return str(path)

    async def _read_text(self, p: Path) -> str:
        relative_path = await run_owned_thread(partial(self._relative_path_for_read, p), label="config-read-path")
        return await self.file_tools.read_file(relative_path)

    async def _exists(self, path: Path) -> bool:
        return await run_owned_thread(path.exists, label="config-path-observation")

    def load_organization(self) -> OrganizationConfig | None:
        return self._run_async(self.load_organization_async())

    async def load_organization_async(self) -> OrganizationConfig | None:
        from orket.schema import OrganizationConfig
        from orket.settings import load_user_settings_async, set_runtime_settings_context

        environment = dict(os.environ if self._environment is None else self._environment)
        org_data = {}

        info_path, arch_path = self.loader_strategy_node.organization_modular_paths(self.config_dir)
        if await self._exists(info_path) and await self._exists(arch_path):
            try:
                info = json.loads(await self._read_text(info_path))
                arch = json.loads(await self._read_text(arch_path))
                org_data = {**info, **arch}
            except (json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
                log_event("config_error", {"error": f"Failed to load modular config: {exc}"})

        if not org_data:
            paths = self.loader_strategy_node.organization_fallback_paths(self.config_dir, self.model_dir)
            for p in paths:
                if await self._exists(p):
                    try:
                        org_data = json.loads(await self._read_text(p))
                        break
                    except (json.JSONDecodeError, OSError, TypeError, ValueError):
                        continue

        if not org_data:
            return None

        try:
            org = OrganizationConfig.model_validate(org_data)
        except (ValidationError, ValueError, TypeError) as exc:
            log_event("config_validation_failed", {"error": str(exc)}, workspace=self.root)
            return None

        settings = json.loads(self._user_settings) if self._user_settings is not None else await load_user_settings_async()
        set_runtime_settings_context(user_settings=settings, environment=environment)
        overrides = {field: value for field, key in (("name", "ORKET_ORG_NAME"), ("vision", "ORKET_ORG_VISION"))
                     if (value := environment.get(key, settings.get(key)))}
        return OrganizationConfig.model_validate({**org.model_dump(), **overrides})

    def load_department(self, name: str) -> DepartmentConfig | None:
        return self._run_async(self.load_department_async(name))

    async def load_department_async(self, name: str) -> DepartmentConfig | None:
        from orket.schema import DepartmentConfig

        paths = self.loader_strategy_node.department_paths(self.config_dir, self.model_dir, name)
        for p in paths:
            if await self._exists(p):
                raw = await self._read_text(p)
                return DepartmentConfig.model_validate_json(raw)
        return None

    def load_asset(self, category: str, name: str, model_type: type[BaseModel]) -> Any:
        return self._run_async(self.load_asset_async(category, name, model_type))

    async def load_asset_async(self, category: str, name: str, model_type: type[BaseModel]) -> Any:
        raw = await self._load_asset_raw_async(category, name, self.department)
        return validate_config_asset_json(model_type, raw, runtime_inputs=self.runtime_inputs)

    async def load_environment_asset_async(self, name: str) -> Any:
        from orket.schema import validate_authoritative_environment_config_json

        raw = await self._load_asset_raw_async("environments", name, self.department)
        return validate_authoritative_environment_config_json(raw)

    def _load_asset_raw(self, category: str, name: str, dept: str) -> str:
        return self._run_async(self._load_asset_raw_async(category, name, dept))

    async def _load_asset_raw_async(self, category: str, name: str, dept: str) -> str:
        paths = self.loader_strategy_node.asset_paths(
            self.config_dir,
            self.model_dir,
            dept,
            category,
            name,
        )

        for p in paths:
            if await self._exists(p):
                return await self._read_text(p)

        raise CardNotFound(f"Asset '{name}' not found in category '{category}' for department '{dept}'.")

    def list_assets(self, category: str) -> list[str]:
        return self._run_async(self.list_assets_async(category))

    async def list_assets_async(self, category: str) -> list[str]:
        def _collect_assets() -> list[str]:
            assets = set()
            search_paths = self.loader_strategy_node.list_asset_search_paths(
                self.config_dir,
                self.model_dir,
                self.department,
                category,
            )
            for p in search_paths:
                if p.exists():
                    for f in p.glob("*.json"):
                        assets.add(f.stem)
            return sorted(list(assets))

        return await run_owned_thread(_collect_assets, label="config-asset-inventory")
