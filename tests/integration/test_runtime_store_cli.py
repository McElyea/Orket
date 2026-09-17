"""Native installed/source CLI proof with retained SQLite as the outcome authority."""

from __future__ import annotations

import os
import sys

import pytest

from orket.application.services.command_process_supervisor import CommandProcessSupervisor
from tests.helpers.runtime_store_migration import legacy_pause
from tests.integration.test_runtime_store_binding import bound_engine

pytestmark = [pytest.mark.asyncio, pytest.mark.end_to_end]


@pytest.mark.parametrize("owners_stopped", [False, True])
# Layer: end-to-end
async def test_native_storage_migration_cli_reports_retained_outcome(tmp_path, monkeypatch, owners_stopped):
    root = tmp_path / "project"
    approval, service = await legacy_pause(root, monkeypatch)
    arguments = [
        sys.executable,
        "-m",
        "orket.interfaces.runtime_store_cli",
        "--runtime-db",
        str(service.binding.runtime_db),
        "--legacy-control-plane-db",
        str(service.source),
        "--legacy-invocation-root",
        str(root),
        "--actor-ref",
        "acceptance:native-cli",
    ]
    if owners_stopped:
        arguments.append("--owners-stopped")
    outcome = await CommandProcessSupervisor(root, cancellation_event="verification_process_cancelled").run(
        arguments, cwd=root, environment=dict(os.environ, ORKET_DISABLE_SANDBOX="1"), timeout_seconds=15
    )
    assert outcome.cleanup_confirmed and outcome.capture_complete
    assert outcome.returncode == (0 if owners_stopped else 1)
    if owners_stopped:
        await service.binding.initialize()
        binding = await service.binding.repository.read_binding(service.binding.runtime_db)
        assert binding is not None and binding.digest().encode() in outcome.stdout
        async with bound_engine(root, root / "workspace", monkeypatch) as engine:
            response = await engine.decide_approval(approval_id=approval["approval_id"], decision="approve")
            assert response["runtime_result"]["succeeded"]
    else:
        assert b"E_RUNTIME_STORE_MIGRATION_OFFLINE_REQUIRED" in outcome.stderr
        assert await service.binding.repository.read_binding(service.binding.runtime_db) is None
