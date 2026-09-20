"""Application ownership of extension command preparation and catalog inspection."""
from orket.adapters.execution.owned_io import run_owned_thread
from orket.extensions.manager import ExtensionManager
from orket.extensions.models import ExtensionRecord


async def prepare_extension_manager() -> ExtensionManager:
    return await run_owned_thread(ExtensionManager, label="extension-manager-construction")


async def list_installed_extensions(manager: ExtensionManager) -> list[ExtensionRecord]:
    return await run_owned_thread(manager.list_extensions, label="extension-list")
