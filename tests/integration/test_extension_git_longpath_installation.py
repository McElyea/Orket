"""Integration: SDK extension installation owns Git through short and long physical paths."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
from dataclasses import replace
from pathlib import Path

import psutil
import pytest

from orket.application.services.command_process_supervisor import CommandProcessSupervisor
from orket.application.services.extension_catalog_commands import (
    list_installed_extensions,
    prepare_extension_manager,
)
from orket.extensions.git_commands import ExtensionGitError
from tests.runtime.test_extension_capability_authorization import MEMORY_QUERY_SOURCE, _init_sdk_repo

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
LONG_OBJECT_MINIMUM = 261
GIT_ATTRIBUTES = b"* -text\n"


@pytest.fixture
def command_receipts(monkeypatch):
    original, receipts = CommandProcessSupervisor.run, []

    async def observe(owner, *args, **kwargs):
        result = await original(owner, *args, **kwargs)
        receipts.append(result)
        return result

    monkeypatch.setattr(CommandProcessSupervisor, "run", observe)
    return receipts


def _git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-c", "core.longpaths=true", *arguments],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout.strip()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_bytes(source: Path) -> dict[str, bytes]:
    return {
        relative: (source / relative).read_bytes()
        for relative in (".gitattributes", "extension.yaml", "sdk_auth_extension.py")
    }


def _commit_object(repository: Path, commit: str) -> Path:
    return repository / ".git" / "objects" / commit[:2] / commit[2:]


def _object_projection(durable_root: Path, commit: str) -> Path:
    return durable_root / "extensions" / "checkout-xxxxxxxx" / _commit_object(Path(), commit)


def _long_durable_root(fixture_root: Path, commit: str) -> Path:
    root = fixture_root / "long-durable"
    while len(str(_object_projection(root, commit))) < LONG_OBJECT_MINIMUM:
        missing = LONG_OBJECT_MINIMUM - len(str(_object_projection(root, commit)))
        root /= "x" * max(1, min(40, missing - 1))
    return root


def _checkout_roots(install_root: Path) -> list[str]:
    return [str(path) for path in sorted(install_root.glob("checkout-*")) if path.is_dir()]


def _record_failure(stage: dict, failure: ExtensionGitError) -> None:
    observed = failure.observation
    stage.update(
        status="failure",
        failure=str(failure),
        reason=observed.reason,
        returncode=observed.returncode,
        cleanup_confirmed=observed.cleanup_confirmed,
        capture_complete=observed.capture_complete,
        stderr_sha256=hashlib.sha256(observed.stderr).hexdigest(),
        filename_too_long=b"Filename too long" in observed.stderr,
    )


async def _assert_processes_stopped(receipts) -> list[int]:
    pids = sorted(
        {
            pid
            for result in receipts
            for pid in (result.transport_pid, result.supervisor_pid, result.command_pid)
            if pid is not None
        }
    )
    assert pids
    running = await asyncio.gather(*(asyncio.to_thread(psutil.pid_exists, pid) for pid in pids))
    assert not any(running)
    return pids


async def _assert_settled(receipts) -> list[int]:
    assert len(receipts) == 3
    expected_backend = "windows_job" if os.name == "nt" else "linux_subreaper"
    assert all(
        result.returncode == 0
        and result.reason == "completed"
        and result.cleanup_confirmed
        and result.capture_complete
        and result.backend == expected_backend
        for result in receipts
    )
    return await _assert_processes_stopped(receipts)


async def _install(
    *, project_root: Path, durable_root: Path, source: Path, expected_commit: str,
    expected_bytes: dict[str, bytes], receipts: list, stage: dict,
) -> int:
    environment = dict(os.environ)
    environment["ORKET_DURABLE_ROOT"] = str(durable_root)
    start = len(receipts)
    manager = await prepare_extension_manager(
        catalog_path=project_root / "extensions_catalog.json",
        project_root=project_root,
        invocation_root=project_root,
        environment=environment,
    )
    assert manager.install_root == durable_root / "extensions"
    stage["manager_install_root"] = str(manager.install_root)
    try:
        record = await manager.install_from_repo(str(source))
    except ExtensionGitError as failure:
        _record_failure(stage, failure)
        assert failure.observation.cleanup_confirmed and failure.observation.capture_complete
        stage["observed_pids_absent_after_return"] = await _assert_processes_stopped([failure.observation])
        stage["retained_checkout_roots"] = await asyncio.to_thread(_checkout_roots, manager.install_root)
        raise
    checkout = Path(record.path)
    commit_object = _commit_object(checkout, expected_commit)
    assert await asyncio.to_thread(commit_object.is_file)
    assert record.resolved_commit_sha == expected_commit
    assert record.source == str(source)
    for relative, content in expected_bytes.items():
        assert await asyncio.to_thread((checkout / relative).read_bytes) == content
    payload = json.loads(await asyncio.to_thread(manager.catalog_path.read_text, encoding="utf-8"))
    assert payload == {"extensions": [manager.catalog.row_from_record(record)]}
    readback = await list_installed_extensions(manager)
    # Preserve the existing generic SDK listing defaults; compare every remaining field.
    assert record.register_callable == ""
    entry, = record.manifest_entries
    assert (entry.input_contract, entry.output_contract) == ("None", "None")
    assert [item for item in readback if item.extension_id == record.extension_id] == [
        replace(record, register_callable="register", manifest_entries=(
            replace(entry, input_contract="", output_contract=""),
        ))
    ]
    observed = receipts[start:]
    stopped = await _assert_settled(observed)
    object_hash = await asyncio.to_thread(_sha256_file, commit_object)
    assert object_hash == stage["source_commit_object"]["sha256"]
    stage.update(
        status="success",
        checkout_root=str(checkout),
        catalog={"path": str(manager.catalog_path),
                 "sha256": await asyncio.to_thread(_sha256_file, manager.catalog_path)},
        installed_commit_object={"path": str(commit_object), "sha256": object_hash,
                                 "length": len(str(commit_object))},
        content_sha256={relative: hashlib.sha256(content).hexdigest()
                        for relative, content in expected_bytes.items()},
        owned_receipts=[
            {"returncode": item.returncode, "reason": item.reason,
             "cleanup_confirmed": item.cleanup_confirmed, "capture_complete": item.capture_complete,
             "backend": item.backend}
            for item in observed
        ],
        receipt_count=len(observed),
        catalog_readback_register_default={"installed": "", "listed": "register"},
        catalog_readback_contract_defaults={"installed": ["None", "None"], "listed": ["", ""]},
        observed_pids_absent_after_return=stopped,
    )
    return len(str(commit_object))


# Layer: integration. Real Git, installed SDK contents, and owned command settlement.
async def test_extension_sdk_installation_supports_actual_git_object_path_over_260(
    tmp_path_factory, command_receipts, record_property,
):
    """Layer: integration. One real SDK source closes short and over-260 owned installation paths."""
    fixture_root = Path(await asyncio.to_thread(tmp_path_factory.mktemp, "extgit"))
    fixture_root = await asyncio.to_thread(fixture_root.resolve)
    observation: dict[str, object] = {
        "schema_version": "extension_git_longpath_observation.v1",
        "fixture_root": str(fixture_root),
    }
    try:
        source = fixture_root / "source"
        await asyncio.to_thread(source.mkdir, parents=True)
        await asyncio.to_thread((source / ".gitattributes").write_bytes, GIT_ATTRIBUTES)
        await asyncio.to_thread(
            _init_sdk_repo,
            source,
            module_source=MEMORY_QUERY_SOURCE,
            required_capabilities=["memory.query"],
        )
        expected_commit = await asyncio.to_thread(_git, source, "rev-parse", "HEAD")
        expected_bytes = await asyncio.to_thread(_source_bytes, source)
        source_object = _commit_object(source, expected_commit)
        assert await asyncio.to_thread(source_object.is_file)
        source_hash = await asyncio.to_thread(_sha256_file, source_object)
        observation.update(
            source_root=str(source),
            source_commit=expected_commit,
            source_commit_object={"path": str(source_object), "sha256": source_hash,
                                  "length": len(str(source_object))},
        )
        short_project, short_durable = fixture_root / "short-project", fixture_root / "d"
        await asyncio.to_thread(short_project.mkdir, parents=True)
        short_projection = _object_projection(short_durable, expected_commit)
        observation["short"] = {
            "project_root": str(short_project), "durable_root": str(short_durable),
            "object_projection": str(short_projection), "projection_length": len(str(short_projection)),
            "source_commit_object": observation["source_commit_object"],
        }
        assert len(str(short_projection)) < 260
        short_length = await _install(
            project_root=short_project, durable_root=short_durable, source=source,
            expected_commit=expected_commit, expected_bytes=expected_bytes,
            receipts=command_receipts, stage=observation["short"],
        )
        assert short_length < 260
        long_project = fixture_root / "long-project"
        long_durable = _long_durable_root(fixture_root, expected_commit)
        await asyncio.to_thread(long_project.mkdir, parents=True)
        long_projection = _object_projection(long_durable, expected_commit)
        observation["long"] = {
            "project_root": str(long_project), "durable_root": str(long_durable),
            "object_projection": str(long_projection), "projection_length": len(str(long_projection)),
            "source_commit_object": observation["source_commit_object"],
        }
        assert len(str(long_projection)) >= LONG_OBJECT_MINIMUM
        long_length = await _install(
            project_root=long_project, durable_root=long_durable, source=source,
            expected_commit=expected_commit, expected_bytes=expected_bytes,
            receipts=command_receipts, stage=observation["long"],
        )
        assert long_length >= LONG_OBJECT_MINIMUM
    finally:
        record_property("extension_git_longpath_observation", json.dumps(observation, sort_keys=True))
