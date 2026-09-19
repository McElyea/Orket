"""Real CLI startup refusal and diagnostic files at the public process boundary."""
from __future__ import annotations

import asyncio
import logging

import pytest

from orket.adapters.storage.local_file_lock import NativeFileLocks
from orket.cli import main
from tests.integration.test_runtime_entrypoints import child

pytestmark = pytest.mark.integration


def test_sequential_cli_invocations_keep_separate_crash_destinations(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ORKET_MODULE_PROFILE", "unknown-crash-fixture")
    roots = [tmp_path / name for name in ("first", "second")]
    try:
        for root in roots:
            root.mkdir()
            monkeypatch.chdir(root)
            assert main(["runtime", "--help"]) == 1
            output = capsys.readouterr()
            target = root / "workspace/default/orket_crash.log"
            assert target.is_file()
            assert "E_MODULE_PROFILE_UNKNOWN" in target.read_text(encoding="utf-8")
            assert str(target) in output.out
    finally:
        # Retain cleanup while this regression is first exercised against the old logger.
        logger = logging.getLogger("orket_crash")
        for handler in tuple(logger.handlers):
            logger.removeHandler(handler)
            handler.close()


def test_cli_diagnostic_failure_keeps_original_error_and_nonzero_return(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ORKET_MODULE_PROFILE", "unknown-crash-fixture")
    target = tmp_path / "workspace/default/orket_crash.log"
    target.mkdir(parents=True)
    assert main(["runtime", "--help"]) == 1
    output = capsys.readouterr()
    assert "E_MODULE_PROFILE_UNKNOWN" in output.out
    assert "Crash report publication failed" in output.err
    assert "saved" not in output.out
    assert target.is_dir()


@pytest.mark.asyncio
@pytest.mark.parametrize("blocked", [False, True])
async def test_public_process_reports_actual_path_or_preserves_publication_failure(tmp_path, blocked):
    target = tmp_path / "workspace/default/orket_crash.log"
    if blocked:
        await asyncio.to_thread(target.mkdir, parents=True)
    code, output, error = await child(
        tmp_path, ["-m", "orket.cli", "runtime", "--help"], profile="unknown-crash-fixture"
    )
    assert code == 1 and "E_MODULE_PROFILE_UNKNOWN" in output
    if blocked:
        assert "Crash report publication failed" in error and "saved" not in output
        assert "E_MODULE_PROFILE_UNKNOWN" in error
    else:
        assert str(target) in output and not error
        assert "E_MODULE_PROFILE_UNKNOWN" in await asyncio.to_thread(target.read_text, encoding="utf-8")


@pytest.mark.asyncio
async def test_public_cli_refuses_another_process_native_owner(tmp_path):
    target = tmp_path / "workspace/default/orket_crash.log"
    locks = NativeFileLocks(target, suffix=".owners", error_prefix="E_CRASH", empty_key_error="E_CRASH_KEY")
    async with locks.hold("append"):
        code, output, error = await child(
            tmp_path, ["-m", "orket.cli", "runtime", "--help"], profile="unknown-crash-fixture"
        )
        assert code == 1 and "owner_busy" in error
        assert "saved" not in output and not await asyncio.to_thread(target.exists)
    code, output, error = await child(
        tmp_path, ["-m", "orket.cli", "runtime", "--help"], profile="unknown-crash-fixture"
    )
    assert code == 1 and str(target) in output and not error
    assert "E_MODULE_PROFILE_UNKNOWN" in await asyncio.to_thread(target.read_text, encoding="utf-8")


def test_cli_retains_invocation_root_when_failed_runtime_changes_directory(tmp_path, monkeypatch, capsys):
    initial, later = tmp_path / "invocation", tmp_path / "later"
    initial.mkdir()
    later.mkdir()
    monkeypatch.chdir(initial)

    async def change_then_fail(*args, **kwargs):
        monkeypatch.chdir(later)
        raise RuntimeError("runtime changed cwd")

    monkeypatch.setattr("orket.interfaces.runtime_entrypoints.create_cli_runtime", lambda: change_then_fail)
    assert main(["runtime"]) == 1
    target = initial / "workspace/default/orket_crash.log"
    assert "runtime changed cwd" in target.read_text(encoding="utf-8")
    assert str(target) in capsys.readouterr().out
    assert not (later / "workspace").exists()
