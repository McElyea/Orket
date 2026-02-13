from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional, Type

from pydantic import BaseModel, ValidationError

from orket.decision_nodes.registry import DecisionNodeRegistry
from orket.exceptions import CardNotFound
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.logging import log_event


class ConfigLoader:
    """
    Unified Configuration and Asset Loader.
    Priority: 1. config/ (Unified) 2. model/{dept}/ (Legacy) 3. model/core/ (Fallback)
    """

    def __init__(
        self,
        root: Path,
        department: str = "core",
        organization: Optional[Any] = None,
        decision_nodes: Optional[DecisionNodeRegistry] = None,
    ):
        self.root = root
        self.config_dir = root / "config"
        self.model_dir = root / "model"
        self.department = department
        self.organization = organization
        self.decision_nodes = decision_nodes or DecisionNodeRegistry()
        self.loader_strategy_node = self.decision_nodes.resolve_loader_strategy(self.organization)
        self.file_tools = AsyncFileTools(self.root)

    def _run_async(self, coro):
        """Run async file ops from sync callers without nested-loop failures."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(coro)).result()

    async def _read_text(self, p: Path) -> str:
        try:
            relative_path = p.resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError:
            relative_path = str(p)
        return await self.file_tools.read_file(relative_path)

    def load_organization(self) -> Optional["OrganizationConfig"]:
        return self._run_async(self.load_organization_async())

    async def load_organization_async(self) -> Optional["OrganizationConfig"]:
        from orket.schema import OrganizationConfig
        from orket.settings import get_setting

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

        return self.loader_strategy_node.apply_organization_overrides(org, get_setting)

    def load_department(self, name: str) -> Optional["DepartmentConfig"]:
        return self._run_async(self.load_department_async(name))

    async def load_department_async(self, name: str) -> Optional["DepartmentConfig"]:
        from orket.schema import DepartmentConfig

        paths = self.loader_strategy_node.department_paths(self.config_dir, self.model_dir, name)
        for p in paths:
            if p.exists():
                raw = await self._read_text(p)
                return DepartmentConfig.model_validate_json(raw)
        return None

    def load_asset(self, category: str, name: str, model_type: Type[BaseModel]) -> Any:
        return self._run_async(self.load_asset_async(category, name, model_type))

    async def load_asset_async(self, category: str, name: str, model_type: Type[BaseModel]) -> Any:
        raw = await self._load_asset_raw_async(category, name, self.department)
        return model_type.model_validate_json(raw)

    @lru_cache(maxsize=256)
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

    def list_assets(self, category: str) -> List[str]:
        return self._run_async(self.list_assets_async(category))

    async def list_assets_async(self, category: str) -> List[str]:
        def _collect_assets() -> List[str]:
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

