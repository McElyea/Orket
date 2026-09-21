"""Application ownership of extension command preparation and catalog inspection."""
from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from functools import partial
from pathlib import Path

from orket.adapters.execution.owned_io import run_owned_thread
from orket.extensions.manager import ExtensionManager
from orket.extensions.models import ExtensionRecord, utc_now_iso


async def prepare_extension_manager(catalog_path: Path | None = None, project_root: Path | None = None,
                                    *, environment: Mapping[str, str] | None = None,
                                    invocation_root: Path | None = None, utc_now: Callable[[], str] = utc_now_iso) -> ExtensionManager:
    root = invocation_root or Path.cwd()
    observed = dict(os.environ if environment is None else environment)
    return await run_owned_thread(partial(ExtensionManager, catalog_path=catalog_path, project_root=project_root,
                                         environment=observed, invocation_root=root, utc_now=utc_now),
                                  label="extension-manager-construction")


async def list_installed_extensions(manager: ExtensionManager) -> list[ExtensionRecord]:
    return await run_owned_thread(manager.list_extensions, label="extension-list")
