"""Explicit application composition for supported project vendors."""
import asyncio
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread
from orket.application.services.local_project_vendor import LocalProjectVendor
from orket.application.services.project_vendor_catalog import ProjectCatalogLocation
from orket.vendors.gitea import GiteaVendor


async def create_project_vendor(
    *, settings: Mapping[str, Any], project_root: Path | None = None, runtime_db: Path | None = None,
) -> LocalProjectVendor | GiteaVendor:
    kind = settings.get("vendor_type", "local")
    if not isinstance(kind, str):
        raise ValueError("E_VENDOR_UNSUPPORTED")
    kind = kind.strip().lower()
    if kind == "local":
        if project_root is None or runtime_db is None or not Path(runtime_db).is_absolute():
            raise ValueError("E_VENDOR_LOCAL_LOCATIONS_REQUIRED")
        location = ProjectCatalogLocation(Path(project_root), settings.get("active_department", "core"))
        return LocalProjectVendor(location, Path(runtime_db))
    if kind != "gitea":
        raise ValueError("E_VENDOR_UNSUPPORTED")
    config = settings.get("gitea_config")
    if not isinstance(config, Mapping):
        raise ValueError("E_VENDOR_GITEA_CONFIGURATION_REQUIRED")
    values = tuple(config.get(key) for key in ("url", "token", "owner", "repo"))
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError("E_VENDOR_GITEA_CONFIGURATION_REQUIRED")
    url, _, owner, repo = values
    try:
        address = urlsplit(url)
        port = address.port
    except ValueError:
        raise ValueError("E_VENDOR_GITEA_URL_INVALID") from None
    if (address.scheme not in {"http", "https"} or not address.hostname or address.username is not None
            or address.password is not None or address.query or address.fragment or port == 0):
        raise ValueError("E_VENDOR_GITEA_URL_INVALID")
    if any(value in {".", ".."} or re.fullmatch(r"[A-Za-z0-9_.-]+", value) is None for value in (owner, repo)):
        raise ValueError("E_VENDOR_GITEA_REPOSITORY_INVALID")
    return await _create_gitea(values)


async def _create_gitea(values: tuple[str, ...]) -> GiteaVendor:
    created = []

    def construct() -> GiteaVendor:
        client = GiteaVendor(*values)
        created.append(client)
        return client

    try:
        return await run_owned_thread(construct, label="project-vendor-http-client")
    except asyncio.CancelledError:
        if created:
            await run_owned_io(created[0].close, label="project-vendor-unadopted-client", preserve_failure=True)
        raise
