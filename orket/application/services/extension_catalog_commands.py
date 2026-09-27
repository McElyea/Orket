"""Application ownership of extension command preparation and catalog inspection."""
from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from pathlib import Path

from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.extensions.manager import ExtensionManager
from orket.extensions.models import ExtensionRecord, utc_now_iso


async def prepare_extension_manager(
    catalog_path: Path | None = None, project_root: Path | None = None, *,
    environment: Mapping[str, str] | None = None, invocation_root: Path | None = None,
    construction_inputs: RuntimeConstructionInputs | None = None,
    utc_now: Callable[[], str] = utc_now_iso,
) -> ExtensionManager:
    if construction_inputs is not None and (environment is not None or invocation_root is not None):
        raise ValueError("E_EXTENSION_CONSTRUCTION_INPUTS_AMBIGUOUS")

    def construct() -> ExtensionManager:
        if construction_inputs is not None:
            return ExtensionManager(
                catalog_path=catalog_path, project_root=project_root,
                construction_inputs=construction_inputs, utc_now=utc_now)
        root = Path.cwd() if invocation_root is None else Path(invocation_root)
        observed = dict(os.environ if environment is None else environment)
        return ExtensionManager(
            catalog_path=catalog_path, project_root=project_root, environment=observed,
            invocation_root=root, utc_now=utc_now)

    return await run_owned_thread(construct, label="extension-manager-construction")


async def list_installed_extensions(manager: ExtensionManager) -> list[ExtensionRecord]:
    return await run_owned_thread(manager.list_extensions, label="extension-list")
