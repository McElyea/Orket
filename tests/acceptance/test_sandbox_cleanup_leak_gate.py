# Layer: end-to-end

from __future__ import annotations

import asyncio
import json
import os
import shutil

import pytest

from orket.domain.sandbox import SandboxRegistry, TechStack
from orket.services.sandbox_orchestrator import SandboxOrchestrator
from tests.acceptance._sandbox_live_ports import patch_orchestrator_port_allocator


pytestmark = pytest.mark.skipif(
    os.getenv("ORKET_RUN_SANDBOX_ACCEPTANCE") != "1",
    reason="Set ORKET_RUN_SANDBOX_ACCEPTANCE=1 to run live sandbox acceptance tests.",
)


def _lightweight_compose(sandbox, _db_password: str) -> str:
    return f"""services:
  api:
    image: nginx:alpine
    labels:
      orket.managed: "true"
      orket.sandbox_id: "{sandbox.id}"
      orket.run_id: "{sandbox.rock_id}"
    ports:
      - "{sandbox.ports.api}:80"
"""


async def _compose_projects() -> set[str]:
    process = await asyncio.create_subprocess_exec(
        "docker-compose",
        "ls",
        "--format",
        "json",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await process.communicate()
    payload = json.loads(stdout.decode() or "[]")
    return {
        str(item.get("Name") or "")
        for item in payload
        if str(item.get("Name") or "").startswith("orket-sandbox-")
    }


async def _compose_cleanup(compose_path: str, compose_project: str) -> None:
    process = await asyncio.create_subprocess_exec(
        "docker-compose",
        "-f",
        compose_path,
        "-p",
        compose_project,
        "down",
        "-v",
        "--remove-orphans",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await process.communicate()


@pytest.mark.asyncio
async def test_live_cleanup_leak_gate_leaves_no_new_sandbox_projects(tmp_path, monkeypatch) -> None:
    if shutil.which("docker-compose") is None:
        pytest.skip("docker-compose is unavailable")

    before = await _compose_projects()
    orchestrator = SandboxOrchestrator(
        workspace_root=tmp_path,
        registry=SandboxRegistry(),
        lifecycle_db_path=str(tmp_path / "sandbox_lifecycle.db"),
    )
    monkeypatch.setattr(orchestrator, "_generate_compose_file", _lightweight_compose)
    patch_orchestrator_port_allocator(orchestrator, monkeypatch)

    compose_project = "orket-sandbox-live-leak-gate-1"
    compose_path = str(orchestrator._compose_path(str(tmp_path)))
    try:
        sandbox = await orchestrator.create_sandbox(
            rock_id="live-leak-gate-1",
            project_name="Live Leak Gate",
            tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
            workspace_path=str(tmp_path),
        )
        await orchestrator.delete_sandbox(sandbox.id)
    finally:
        await _compose_cleanup(compose_path, compose_project)

    after = await _compose_projects()
    for _ in range(10):
        if after - before == set():
            break
        await asyncio.sleep(0.2)
        after = await _compose_projects()

    assert after - before == set()
