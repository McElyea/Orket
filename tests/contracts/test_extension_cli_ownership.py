"""Contract: CLI enters application-owned construction and listing workers."""
import asyncio
from types import SimpleNamespace

import pytest

from orket.application.services import extension_catalog_commands
from orket.interfaces import cli

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


async def test_cli_extension_command_uses_both_owned_workers(monkeypatch):
    observed = []

    def record(stage):
        with pytest.raises(RuntimeError, match="no running event loop"):
            asyncio.get_running_loop()
        observed.append(stage)

    class Manager:
        def __init__(self):
            record("construct")

        def list_extensions(self):
            record("list")
            return []

    async def startup(_setup):
        return {}

    monkeypatch.setattr(extension_catalog_commands, "ExtensionManager", Manager)
    monkeypatch.setattr(cli, "run_startup_checks", startup)
    monkeypatch.setattr(cli, "parse_args", lambda: SimpleNamespace(command="extensions", subcommand="list"))
    monkeypatch.setattr(cli.sys, "platform", "linux")
    assert await cli.run_cli() == 0
    assert observed == ["construct", "list"]
