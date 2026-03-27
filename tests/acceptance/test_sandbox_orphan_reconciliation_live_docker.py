# Layer: end-to-end

from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path

import pytest

from orket.core.domain.sandbox_lifecycle import TerminalReason
from orket.domain.sandbox import SandboxRegistry
from orket.services.sandbox_orchestrator import SandboxOrchestrator


pytestmark = pytest.mark.skipif(
    os.getenv("ORKET_RUN_SANDBOX_ACCEPTANCE") != "1",
    reason="Set ORKET_RUN_SANDBOX_ACCEPTANCE=1 to run live sandbox acceptance tests.",
)


async def _compose_up(compose_dir: Path, compose_project: str) -> None:
    process = await asyncio.create_subprocess_exec(
        "docker-compose",
        "-f",
        str(compose_dir / "docker-compose.yml"),
        "-p",
        compose_project,
        "up",
        "-d",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode:
        raise RuntimeError((stderr or stdout).decode())


async def _compose_down(compose_dir: Path, compose_project: str) -> None:
    process = await asyncio.create_subprocess_exec(
        "docker-compose",
        "-f",
        str(compose_dir / "docker-compose.yml"),
        "-p",
        compose_project,
        "down",
        "-v",
        "--remove-orphans",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await process.communicate()


async def _docker_rows(*cmd: str) -> list[dict[str, object]]:
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await process.communicate()
    rows: list[dict[str, object]] = []
    for line in stdout.decode().splitlines():
        token = line.strip()
        if token:
            rows.append(json.loads(token))
    return rows


@pytest.mark.asyncio
async def test_live_orphan_discovery_classifies_verified_and_unverified_projects(tmp_path) -> None:
    if shutil.which("docker-compose") is None or shutil.which("docker") is None:
        pytest.skip("docker tooling is unavailable")

    verified_project = "orket-sandbox-orphan-live-verified-1"
    unverified_project = "orket-sandbox-orphan-live-unverified-1"
    verified_dir = tmp_path / "verified"
    unverified_dir = tmp_path / "unverified"
    verified_dir.mkdir()
    unverified_dir.mkdir()
    (verified_dir / "docker-compose.yml").write_text(
        """services:
  api:
    image: nginx:alpine
    labels:
      orket.managed: "true"
      orket.sandbox_id: "orphan-live-verified-1"
      orket.run_id: "orphan-live-run-1"
""",
        encoding="utf-8",
    )
    (unverified_dir / "docker-compose.yml").write_text(
        """services:
  api:
    image: nginx:alpine
""",
        encoding="utf-8",
    )

    orchestrator = SandboxOrchestrator(
        workspace_root=tmp_path,
        registry=SandboxRegistry(),
        lifecycle_db_path=str(tmp_path / "sandbox_lifecycle.db"),
    )
    try:
        await _compose_up(verified_dir, verified_project)
        await _compose_up(unverified_dir, unverified_project)

        await orchestrator.discover_orphaned_sandboxes()

        records = {
            record.compose_project: record
            for record in await orchestrator.lifecycle_service.repository.list_records()
            if record.compose_project in {verified_project, unverified_project}
        }

        assert records[verified_project].terminal_reason is TerminalReason.ORPHAN_DETECTED
        assert records[verified_project].cleanup_due_at is not None
        assert records[unverified_project].terminal_reason is TerminalReason.ORPHAN_UNVERIFIED_OWNERSHIP
        assert records[unverified_project].cleanup_due_at is None
    finally:
        await _compose_down(verified_dir, verified_project)
        await _compose_down(unverified_dir, unverified_project)


@pytest.mark.asyncio
async def test_live_verified_orphan_is_cleaned_by_fallback_sweeper_without_compose_path(tmp_path) -> None:
    if shutil.which("docker-compose") is None or shutil.which("docker") is None:
        pytest.skip("docker tooling is unavailable")

    verified_project = "orket-sandbox-orphan-live-cleanup-1"
    verified_dir = tmp_path / "verified-cleanup"
    verified_dir.mkdir()
    (verified_dir / "docker-compose.yml").write_text(
        """services:
  api:
    image: nginx:alpine
    labels:
      orket.managed: "true"
      orket.sandbox_id: "orphan-live-cleanup-1"
      orket.run_id: "orphan-live-cleanup-run-1"
volumes:
  sandbox-data:
    labels:
      orket.managed: "true"
      orket.sandbox_id: "orphan-live-cleanup-1"
      orket.run_id: "orphan-live-cleanup-run-1"
networks:
  default:
    labels:
      orket.managed: "true"
      orket.sandbox_id: "orphan-live-cleanup-1"
      orket.run_id: "orphan-live-cleanup-run-1"
""",
        encoding="utf-8",
    )

    orchestrator = SandboxOrchestrator(
        workspace_root=tmp_path,
        registry=SandboxRegistry(),
        lifecycle_db_path=str(tmp_path / "sandbox_lifecycle.db"),
    )
    try:
        await _compose_up(verified_dir, verified_project)
        await orchestrator.discover_orphaned_sandboxes()
        record = next(
            record
            for record in await orchestrator.lifecycle_service.repository.list_records()
            if record.compose_project == verified_project
        )
        await orchestrator.lifecycle_service.repository.save_record(
            record.model_copy(update={"record_version": record.record_version + 1, "cleanup_due_at": record.created_at})
        )

        swept = await orchestrator.sweep_due_cleanups(max_records=1)
        stored = await orchestrator.lifecycle_service.repository.get_record("orphan-live-cleanup-1")
        containers = await _docker_rows(
            "docker",
            "ps",
            "-a",
            "--filter",
            f"label=com.docker.compose.project={verified_project}",
            "--format",
            "{{json .}}",
        )

        assert len(swept) in {0, 1}
        assert stored is not None
        assert stored.state.value == "cleaned"
        assert stored.terminal_reason == TerminalReason.ORPHAN_DETECTED
        assert containers == []
    finally:
        await _compose_down(verified_dir, verified_project)
