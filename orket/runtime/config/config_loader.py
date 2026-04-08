from __future__ import annotations

import asyncio
import json
from collections.abc import Coroutine
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel, ValidationError

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.decision_nodes.registry import DecisionNodeRegistry
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
    ) -> None:
        self.root = root
        self.config_dir = root / "config"
        self.model_dir = root / "model"
        self.department = department
        self.organization = organization
        self.decision_nodes = decision_nodes or DecisionNodeRegistry()
        self.loader_strategy_node = self.decision_nodes.resolve_loader_strategy(self.organization)
        self.file_tools = AsyncFileTools(self.root)

    def _run_async(self, coro: Coroutine[Any, Any, T]) -> T:
        """Run async file ops from sync callers without nested-loop failures."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(coro)).result()

    def _relative_path_for_read(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return str(path)

    async def _read_text(self, p: Path) -> str:
        relative_path = await asyncio.to_thread(self._relative_path_for_read, p)
        return await self.file_tools.read_file(relative_path)

    def load_organization(self) -> OrganizationConfig | None:
        return self._run_async(self.load_organization_async())

    async def load_organization_async(self) -> OrganizationConfig | None:
        from orket.schema import OrganizationConfig
        from orket.settings import get_setting, load_user_settings_async, set_runtime_settings_context

        org_data = {}

        info_path, arch_path = self.loader_strategy_node.organization_modular_paths(self.config_dir)
        if info_path.exists() and arch_path.exists():
            try:
                info = json.loads(await self._read_text(info_path))
                arch = json.loads(await self._read_text(arch_path))
                org_data = {**info, **arch}
            except (json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
                log_event("config_error", {"error": f"Failed to load modular config: {exc}"})

        if not org_data:
            paths = self.loader_strategy_node.organization_fallback_paths(self.config_dir, self.model_dir)
            for p in paths:
                if p.exists():
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

        set_runtime_settings_context(user_settings=await load_user_settings_async())
        overridden = self.loader_strategy_node.apply_organization_overrides(org, get_setting)
        return overridden if isinstance(overridden, OrganizationConfig) else org

    def load_department(self, name: str) -> DepartmentConfig | None:
        return self._run_async(self.load_department_async(name))

    async def load_department_async(self, name: str) -> DepartmentConfig | None:
        from orket.schema import DepartmentConfig

        paths = self.loader_strategy_node.department_paths(self.config_dir, self.model_dir, name)
        for p in paths:
            if p.exists():
                raw = await self._read_text(p)
                return DepartmentConfig.model_validate_json(raw)
        return None

    def load_asset(self, category: str, name: str, model_type: type[BaseModel]) -> Any:
        return self._run_async(self.load_asset_async(category, name, model_type))

    async def load_asset_async(self, category: str, name: str, model_type: type[BaseModel]) -> Any:
        raw = await self._load_asset_raw_async(category, name, self.department)
        return model_type.model_validate_json(raw)

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
            if p.exists():
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

        return await asyncio.to_thread(_collect_assets)
