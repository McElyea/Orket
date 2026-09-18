"""Real settings files, restart, competing processes and owned interruption."""
# Layer: integration
from __future__ import annotations

import asyncio
import json
import sys
import threading
from pathlib import Path

import pytest

from orket import settings
from orket.adapters.storage.settings_file_store import hold_settings_files

pytestmark = pytest.mark.integration
PENDING = "legacy_model_preferences_pending_v1"
MARKER = "legacy_model_preferences_v1"
RESPONSIVENESS_SECONDS = 0.5


def _paths(tmp_path):
    first, second = tmp_path / "settings.json", tmp_path / "preferences.json"
    settings.set_settings_file(first)
    settings.set_preferences_file(second)
    return first, second


async def _child(operation, first, second):
    process = await asyncio.create_subprocess_exec(sys.executable, "-m", "tests.helpers.settings_worker",
        operation, str(first), str(second), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), 15)
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()
    assert not stderr, stderr.decode()
    return process.returncode, json.loads(stdout)


@pytest.mark.asyncio
async def test_preference_migration_resumes_in_new_process_after_settings_write_failure(monkeypatch, tmp_path):
    first, second = _paths(tmp_path)
    first.write_text(json.dumps({"preferred_coder": "captured", "keep": 17}), encoding="utf-8")
    replace = Path.replace

    def fail_settings_publication(source, target):
        if target == first:
            raise OSError("injected settings publication failure")
        return replace(source, target)

    with monkeypatch.context() as fault:
        fault.setattr(Path, "replace", fail_settings_publication)
        with pytest.raises(OSError, match="publication failure"):
            await settings.load_user_preferences_async()
    pending = json.loads(second.read_text(encoding="utf-8"))
    assert pending["_meta"][PENDING]["values"] == {"preferred_coder": "captured"}
    assert not pending["_meta"]["migration_markers"].get(MARKER)
    assert json.loads(first.read_text(encoding="utf-8"))["preferred_coder"] == "captured"
    with pytest.raises(ValueError, match="MIGRATION_PENDING"):
        await settings.save_user_settings_async({"overwrite": True})
    code, observed = await _child("preferences", first, second)
    assert code == 0 and observed["models"] == {"coder": "captured"}
    assert observed["_meta"]["migration_markers"][MARKER] is True
    assert PENDING not in observed["_meta"]
    assert json.loads(first.read_text(encoding="utf-8")) == {"keep": 17}
    assert not list(tmp_path.glob(".*.tmp"))


@pytest.mark.asyncio
@pytest.mark.parametrize("drift", ["settings_path", "models", "legacy_value", "legacy_value_type", "pending_record"])
async def test_pending_migration_rejects_drift_without_writing(tmp_path, drift):
    first, second = _paths(tmp_path)
    old = {"preferred_coder": "original"}
    pending = {"settings_path": str(first), "values": dict(old)}
    preferences = {"models": {"coder": "original"}, "_meta": {PENDING: pending, "migration_markers": {}}}
    if drift == "settings_path":
        pending["settings_path"] = str(tmp_path / "other.json")
    elif drift == "models":
        preferences["models"]["coder"] = "changed"
    elif drift == "legacy_value_type":
        pending["values"]["preferred_coder"] = 1
        preferences["models"]["coder"] = "1"
        old["preferred_coder"] = True
    elif drift == "pending_record":
        preferences["_meta"][PENDING] = None
    else:
        old["preferred_coder"] = "changed"
    first.write_text(json.dumps(old), encoding="utf-8")
    second.write_text(json.dumps(preferences), encoding="utf-8")
    before = first.read_bytes(), second.read_bytes()
    with pytest.raises(ValueError, match="MIGRATION"):
        await settings.load_user_preferences_async()
    assert (first.read_bytes(), second.read_bytes()) == before


@pytest.mark.asyncio
async def test_competing_process_refuses_admitted_write_and_releases_all_locks(tmp_path):
    first, second = _paths(tmp_path)
    first.write_text('{"original": true}', encoding="utf-8")
    with hold_settings_files((first, second)):
        code, result = await _child("save", first, second)
        assert code == 2 and "owner_busy" in result["error"]
        assert json.loads(first.read_text(encoding="utf-8")) == {"original": True}
    code, result = await _child("save", first, second)
    assert code == 0 and result == {"saved": True}
    assert json.loads(first.read_text(encoding="utf-8")) == {"from_process": True}


@pytest.mark.asyncio
async def test_admitted_write_keeps_paths_while_independent_read_remains_responsive(monkeypatch, tmp_path):
    first, second = _paths(tmp_path / "one")
    other = tmp_path / "two.json"
    other.write_text('{"selected": "two"}', encoding="utf-8")
    entered, release = threading.Event(), threading.Event()
    real_replace = Path.replace

    def hold_replace(source, target):
        if target == first:
            entered.set()
            assert release.wait(5)
        return real_replace(source, target)

    monkeypatch.setattr(Path, "replace", hold_replace)
    task = asyncio.create_task(settings.save_user_settings_async({"selected": "one"}))
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        settings.set_settings_file(other)
        observed = await asyncio.wait_for(settings.load_user_settings_async(), RESPONSIVENESS_SECONDS)
        assert observed == {"selected": "two"}
    finally:
        release.set()
        await task
    assert json.loads(first.read_text(encoding="utf-8")) == {"selected": "one"}
    assert json.loads(other.read_text(encoding="utf-8")) == {"selected": "two"}
    assert not second.exists()


@pytest.mark.asyncio
async def test_worker_failure_after_cancel_is_observed_and_old_file_retained(monkeypatch, tmp_path):
    first, _ = _paths(tmp_path)
    first.write_text('{"original": true}', encoding="utf-8")
    entered, release = threading.Event(), threading.Event()
    replace = Path.replace

    def fail_replace(source, target):
        if target == first:
            entered.set()
            assert release.wait(5)
            raise OSError("owned settings failure")
        return replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_replace)
    task = asyncio.create_task(settings.save_user_settings_async({"new": True}))
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        task.cancel()
        await asyncio.sleep(0)
    finally:
        release.set()
        with pytest.raises(OSError, match="owned settings failure"):
            await task
    assert json.loads(first.read_text(encoding="utf-8")) == {"original": True}
    assert not list(tmp_path.glob(".*.tmp"))


def test_runtime_get_setting_retains_captured_environment(monkeypatch):
    monkeypatch.setenv("SD_MODEL", "captured")
    settings.set_runtime_settings_context(user_settings={"sd_model": "fallback"})
    monkeypatch.setenv("SD_MODEL", "later")
    assert settings.get_setting("sd_model") == "captured"


@pytest.mark.asyncio
async def test_async_persistence_read_does_not_replace_explicit_runtime_snapshot(tmp_path):
    first, _ = _paths(tmp_path)
    first.write_text('{"selected": "stored"}', encoding="utf-8")
    settings.set_runtime_settings_context(user_settings={"selected": "runtime"})
    assert await settings.load_user_settings_async() == {"selected": "stored"}
    assert settings.load_user_settings() == {"selected": "runtime"}


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", ['[]', '{"value": NaN}', '{"value": 1e999}', '{"value": 1, "value": 2}'])
async def test_invalid_settings_values_refuse_without_mutation(tmp_path, raw):
    first, _ = _paths(tmp_path)
    first.write_text(raw, encoding="utf-8")
    with pytest.raises(ValueError):
        await settings.load_user_settings_async()
    assert first.read_text(encoding="utf-8") == raw


@pytest.mark.asyncio
async def test_missing_file_and_observation_failure_have_distinct_results(monkeypatch, tmp_path):
    first, _ = _paths(tmp_path)
    assert await settings.load_user_settings_async() == {}
    read_bytes = Path.read_bytes

    def deny_selected(path):
        if path == first:
            raise PermissionError("injected unreadable settings")
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", deny_selected)
    with pytest.raises(PermissionError, match="unreadable settings"):
        await settings.load_user_settings_async()


@pytest.mark.asyncio
async def test_marked_legacy_migration_only_finishes_matching_prior_models(tmp_path):
    first, second = _paths(tmp_path)
    first.write_text('{"preferred_coder": "original", "keep": true}', encoding="utf-8")
    second.write_text(json.dumps({"models": {"coder": "different"},
        "_meta": {"migration_markers": {MARKER: True}}}), encoding="utf-8")
    with pytest.raises(ValueError, match="MIGRATION_CONFLICT"):
        await settings.load_user_preferences_async()
    assert "preferred_coder" in json.loads(first.read_text(encoding="utf-8"))
    preferences = json.loads(second.read_text(encoding="utf-8"))
    preferences["models"]["coder"] = "original"
    second.write_text(json.dumps(preferences), encoding="utf-8")
    assert (await settings.load_user_preferences_async())["models"] == {"coder": "original"}
    assert json.loads(first.read_text(encoding="utf-8")) == {"keep": True}



@pytest.mark.asyncio
async def test_preference_save_retains_exact_supplied_metadata_shape(tmp_path):
    _, preferences = _paths(tmp_path)
    payload = {"models": {"coder": "captured"}}
    await settings.save_user_preferences_async(payload)
    assert json.loads(preferences.read_text(encoding="utf-8")) == payload


@pytest.mark.asyncio
async def test_conditional_save_distinguishes_boolean_and_numeric_inputs(tmp_path):
    from orket.application.services.user_settings_service import SettingsUpdateConflict

    path, _ = _paths(tmp_path)
    path.write_text('{"enabled": true}', encoding="utf-8")
    with pytest.raises(SettingsUpdateConflict):
        await settings.save_user_settings_async({"enabled": False}, expected={"enabled": 1})
    assert json.loads(path.read_text(encoding="utf-8")) == {"enabled": True}
    await settings.save_user_settings_async({"enabled": False}, expected={"enabled": True})
    assert json.loads(path.read_text(encoding="utf-8")) == {"enabled": False}



@pytest.mark.asyncio
async def test_absent_legacy_settings_does_not_create_legacy_lock_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ORKET_DURABLE_ROOT", raising=False)
    settings.clear_settings_cache()
    observed = await settings.load_user_preferences_async()
    assert observed["_meta"]["migration_markers"][MARKER] is True
    assert (tmp_path / ".orket/durable/config/preferences.json").is_file()
    assert not (tmp_path / "user_settings.json.settings-locks").exists()


@pytest.mark.asyncio
async def test_startup_binds_persisted_inputs_in_the_calling_task(tmp_path):
    from orket.discovery import run_startup_checks

    first, second = _paths(tmp_path)
    first.write_text('{"preferred_coder": "migrated", "keep": 17}', encoding="utf-8")
    settings.clear_runtime_settings_context()
    status = await run_startup_checks(lambda: {"reconciliation": "success", "onboarding": "no_op"})
    assert status == {"reconciliation": "success", "onboarding": "no_op"}
    assert settings.load_user_settings() == {"keep": 17}
    assert settings.load_user_preferences()["models"] == {"coder": "migrated"}
    assert json.loads(first.read_text(encoding="utf-8")) == {"keep": 17}
    assert json.loads(second.read_text(encoding="utf-8"))["_meta"]["migration_markers"][MARKER] is True


@pytest.mark.asyncio
async def test_legacy_retirement_refuses_json_type_change_after_publication(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ORKET_DURABLE_ROOT", raising=False)
    settings.clear_settings_cache()
    legacy = tmp_path / "user_settings.json"
    legacy.write_text('{"value": 1}', encoding="utf-8")
    target = tmp_path / ".orket/durable/config/user_settings.json"
    replace = Path.replace

    def replace_then_change_legacy(source, destination):
        result = replace(source, destination)
        if destination == target:
            legacy.write_text('{"value": true}', encoding="utf-8")
        return result

    monkeypatch.setattr(Path, "replace", replace_then_change_legacy)
    with pytest.raises(ValueError, match="LEGACY_CHANGED"):
        await settings.load_user_settings_async()
    assert json.loads(target.read_text(encoding="utf-8")) == {"value": 1}
    assert json.loads(legacy.read_text(encoding="utf-8")) == {"value": True}
