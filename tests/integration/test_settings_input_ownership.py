"""Real-file settings capture and interruption contracts."""
# Layer: integration
from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path

import pytest

import orket.settings as settings

pytestmark = pytest.mark.integration


def test_runtime_snapshot_detaches_nested_input_and_exports() -> None:
    source = {"policy": {"blocked": ["original"]}}
    settings.set_runtime_settings_context(user_settings=source)
    source["policy"]["blocked"].append("caller")
    exported = settings.load_user_settings()
    exported["policy"]["blocked"].append("consumer")
    assert settings.load_user_settings() == {"policy": {"blocked": ["original"]}}


def test_runtime_preferences_detach_nested_input_and_exports() -> None:
    source = {"models": {"coder": "original"}}
    settings.set_runtime_settings_context(user_preferences=source)
    source["models"]["coder"] = "caller"
    exported = settings.load_user_preferences()
    exported["models"]["coder"] = "consumer"
    assert settings.load_user_preferences() == {"models": {"coder": "original"}}


def test_persisted_settings_do_not_return_mutated_cache(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    path = tmp_path / "settings.json"
    settings.set_settings_file(path)
    source = {"policy": {"blocked": ["original"]}}
    settings.save_user_settings(source)
    source["policy"]["blocked"].append("caller")
    first = settings.load_user_settings()
    first["policy"]["blocked"].append("consumer")
    assert settings.load_user_settings() == json.loads(path.read_text(encoding="utf-8"))


def test_default_settings_follow_selected_invocation_root(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    settings.clear_settings_cache()
    for name in ("one", "two"):
        root = tmp_path / name
        path = root / ".orket/durable/config/user_settings.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"root": name}), encoding="utf-8")
        monkeypatch.chdir(root)
        monkeypatch.delenv("ORKET_DURABLE_ROOT", raising=False)
        assert settings.load_user_settings() == {"root": name}


@pytest.mark.asyncio
async def test_malformed_settings_refuse_empty_success(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{broken", encoding="utf-8")
    settings.set_settings_file(path)
    with pytest.raises(ValueError):
        await settings.load_user_settings_async()
    assert path.read_text(encoding="utf-8") == "{broken"


@pytest.mark.asyncio
async def test_settings_write_captures_input_and_retains_cancelled_worker(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "owned" / "settings.json"
    settings.set_settings_file(path)
    entered, release, settled = threading.Event(), threading.Event(), threading.Event()
    real_mkdir = Path.mkdir

    def held_mkdir(target, *args, **kwargs):
        if target == path.parent:
            entered.set()
            assert release.wait(5), "test did not release owned settings worker"
            try:
                return real_mkdir(target, *args, **kwargs)
            finally:
                settled.set()
        return real_mkdir(target, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", held_mkdir)
    payload = {"models": {"coder": "original"}}
    task = asyncio.create_task(settings.save_user_settings_async(payload))
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        payload["models"]["coder"] = "mutated"
        task.cancel()
        await asyncio.sleep(0.02)
        task.cancel()
        await asyncio.sleep(0.02)
        retained = not task.done()
    finally:
        release.set()
        result = await asyncio.gather(task, return_exceptions=True)
        assert await asyncio.to_thread(settled.wait, 3)
    assert retained, "caller returned before the admitted settings worker settled"
    assert isinstance(result[0], asyncio.CancelledError)
    assert json.loads(path.read_text(encoding="utf-8")) == {"models": {"coder": "original"}}


@pytest.mark.asyncio
async def test_cold_sync_read_in_loop_refuses_without_filesystem_probe(monkeypatch, tmp_path: Path) -> None:
    settings.set_settings_file(tmp_path / "missing.json")
    settings.clear_runtime_settings_context()
    observed = []
    real_exists = Path.exists

    def record_exists(path):
        observed.append(path)
        return real_exists(path)

    monkeypatch.setattr(Path, "exists", record_exists)
    with pytest.raises(settings.SettingsBridgeError):
        settings.load_user_settings()
    assert not observed
