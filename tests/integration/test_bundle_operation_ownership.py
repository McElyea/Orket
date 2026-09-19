"""Layer: integration. Real bundle files, verified archives and retained worker lifetime."""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import threading
import zipfile
from pathlib import Path

import pytest

from orket.adapters.storage import bundle_store
from orket.application.services.bundle_service import BundleService
from tests.interfaces.test_orket_bundle_cli import _create_valid_bundle

pytestmark = pytest.mark.integration
# Declare responsiveness/settlement bounds before measuring either operation.
RESPONSIVENESS_SECONDS = 0.5
SETTLEMENT_SECONDS = 3.0


def _archive_bytes(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


@pytest.mark.asyncio
async def test_pack_keeps_crlf_manifest_and_deterministic_member_bytes(tmp_path: Path) -> None:
    await asyncio.to_thread(_create_valid_bundle, tmp_path / "source")
    manifest = tmp_path / "source/orket.json"
    raw = (await asyncio.to_thread(manifest.read_bytes)).replace(b"\n", b"\r\n")
    await asyncio.to_thread(manifest.write_bytes, raw)
    service = BundleService(engine_version="0.6.24")
    one, two = tmp_path / "one.orket", tmp_path / "two.orket"
    assert (await service.pack(manifest.parent, out_path=one))["ok"]
    assert (await service.pack(manifest.parent, out_path=two))["ok"]
    one_bytes, two_bytes = await asyncio.gather(asyncio.to_thread(one.read_bytes), asyncio.to_thread(two.read_bytes))
    assert hashlib.sha256(one_bytes).digest() == hashlib.sha256(two_bytes).digest()
    members = await asyncio.to_thread(_archive_bytes, one)
    assert members["orket.json"] == raw
    assert (await service.inspect(one))["ok"]


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["manifest", "reference", "invalid_utf8"])
async def test_pack_rejects_changed_admitted_source_without_replacing_destination(tmp_path: Path, change: str) -> None:
    source, destination = tmp_path / "source", tmp_path / "existing.orket"
    await asyncio.to_thread(_create_valid_bundle, source)
    await asyncio.to_thread(destination.write_bytes, b"retained destination")

    class ChangingStore(bundle_store.BundleStore):
        async def pack(self, captured, selected, required_names):
            if change == "manifest":
                await asyncio.to_thread((source / "orket.json").write_text, "{}", encoding="utf-8")
            elif change == "invalid_utf8":
                await asyncio.to_thread((source / "orket.json").write_bytes, b"\xff")
            else:
                await asyncio.to_thread((source / "state_machine.json").unlink)
            return await super().pack(captured, selected, required_names)

    result = await BundleService(store=ChangingStore()).pack(source, out_path=destination)
    assert result["ok"] is False
    assert result["errors"][0]["code"] == "E_PACK_SOURCE_CHANGED"
    assert await asyncio.to_thread(destination.read_bytes) == b"retained destination"
    assert not await asyncio.to_thread(lambda: list(tmp_path.glob(".orket-bundle-*")))


@pytest.mark.asyncio
@pytest.mark.parametrize("interrupt", ["cancel", "timeout"])
async def test_packing_stays_responsive_and_drains_interrupted_worker(tmp_path: Path, monkeypatch, interrupt: str) -> None:
    source, destination = tmp_path / "source", tmp_path / "packed.orket"
    await asyncio.to_thread(_create_valid_bundle, source)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = bundle_store._write_archive

    def held_write(path, entries):
        entered.set()
        assert release.wait(SETTLEMENT_SECONDS), "test did not release its owned worker"
        try:
            return original(path, entries)
        finally:
            finished.set()

    monkeypatch.setattr(bundle_store, "_write_archive", held_write)
    service = BundleService()
    operation = asyncio.create_task(service.pack(source, out_path=destination))
    waiter = None
    try:
        assert await asyncio.to_thread(entered.wait, SETTLEMENT_SECONDS)
        assert (await asyncio.wait_for(service.validate(source), RESPONSIVENESS_SECONDS))["ok"]
        if interrupt == "cancel":
            operation.cancel()
            await asyncio.sleep(0)
            operation.cancel()
            waiter = operation
        else:
            waiter = asyncio.create_task(asyncio.wait_for(operation, timeout=0.01))
            await asyncio.sleep(0.03)
        assert not operation.done()
        assert not finished.is_set()
    finally:
        release.set()
        if waiter is not None:
            with pytest.raises(asyncio.CancelledError if interrupt == "cancel" else TimeoutError):
                await asyncio.wait_for(waiter, SETTLEMENT_SECONDS)
        else:
            await asyncio.wait_for(operation, SETTLEMENT_SECONDS)
    assert finished.is_set()
    # Cancellation is delivered after the admitted effect settles; it does not promise rollback.
    assert (await service.inspect(destination))["ok"]
    assert not await asyncio.to_thread(lambda: list(tmp_path.glob(".orket-bundle-*")))


@pytest.mark.asyncio
async def test_failed_archive_verification_preserves_destination_and_cleans_temporary(tmp_path: Path, monkeypatch) -> None:
    source, destination = tmp_path / "source", tmp_path / "existing.orket"
    await asyncio.to_thread(_create_valid_bundle, source)
    await asyncio.to_thread(destination.write_bytes, b"retained destination")
    original = bundle_store._write_archive

    def corrupt_after_write(path, entries):
        hashes = original(path, entries)
        path.write_bytes(b"corrupt archive")
        return hashes

    monkeypatch.setattr(bundle_store, "_write_archive", corrupt_after_write)
    with pytest.raises(zipfile.BadZipFile):
        await BundleService().pack(source, out_path=destination)
    assert await asyncio.to_thread(destination.read_bytes) == b"retained destination"
    assert not await asyncio.to_thread(lambda: list(tmp_path.glob(".orket-bundle-*")))


@pytest.mark.asyncio
async def test_invalid_yaml_returns_parse_failure(tmp_path: Path) -> None:
    await asyncio.to_thread((tmp_path / "orket.yaml").write_text, "model: [", encoding="utf-8")
    result = await BundleService().validate(tmp_path)
    assert result["ok"] is False
    assert result["errors"][0]["code"] == "E_MANIFEST_PARSE"


@pytest.mark.asyncio
async def test_reference_outside_root_is_not_admitted(tmp_path: Path) -> None:
    source = tmp_path / "source"
    await asyncio.to_thread(_create_valid_bundle, source)
    manifest = source / "orket.json"
    payload = json.loads(await asyncio.to_thread(manifest.read_text, encoding="utf-8"))
    payload["stateMachine"]["file"] = "../outside.json"
    await asyncio.to_thread(manifest.write_text, json.dumps(payload), encoding="utf-8")
    await asyncio.to_thread((tmp_path / "outside.json").write_text, "{}", encoding="utf-8")
    result = await BundleService().validate(source)
    assert result["ok"] is False
    assert result["errors"][0]["code"] == "E_STATE_MACHINE_MISSING"


@pytest.mark.asyncio
async def test_real_cli_packs_and_inspects_from_foreign_working_directory(tmp_path: Path) -> None:
    source, destination = tmp_path / "source", tmp_path / "bundle.orket"
    await asyncio.to_thread(_create_valid_bundle, source)

    async def invoke(*arguments):
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "orket.interfaces.orket_bundle_cli", *arguments,
            cwd=tmp_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(process.communicate(), timeout=30)
        finally:
            if process.returncode is None:
                process.kill()
                await process.communicate()
        assert process.returncode == 0, (out.decode(), err.decode())
        return json.loads(out)

    validated = await invoke("validate", str(source), "--json")
    packed = await invoke("pack", str(source), "--out", str(destination), "--json")
    inspected = await invoke("inspect", str(destination), "--json")
    assert validated["ok"] and packed["ok"] and inspected["ok"]
    assert inspected["entry_count"] == packed["file_count"]
    members = await asyncio.to_thread(_archive_bytes, destination)
    assert "orket.json" in members and "state_machine.json" in members


@pytest.mark.asyncio
async def test_archive_invalid_utf8_is_reported_as_parse_failure(tmp_path: Path) -> None:
    target = tmp_path / "invalid.orket"

    def create():
        with zipfile.ZipFile(target, "w") as archive:
            archive.writestr("orket.json", b"\xff")

    await asyncio.to_thread(create)
    result = await BundleService().inspect(target)
    assert result["ok"] is False
    assert result["errors"][0]["code"] == "E_MANIFEST_PARSE"
    assert result["errors"][0]["location"] == "orket.json"


@pytest.mark.asyncio
async def test_directory_invalid_utf8_reports_manifest_location(tmp_path: Path) -> None:
    await asyncio.to_thread((tmp_path / "orket.json").write_bytes, b"\xff")
    result = await BundleService().validate(tmp_path)
    assert result["ok"] is False
    assert result["errors"][0]["code"] == "E_MANIFEST_PARSE"
    assert result["errors"][0]["location"] == "orket.json"


@pytest.mark.asyncio
async def test_validation_captures_selected_store_version_and_models_before_await(tmp_path: Path) -> None:
    await asyncio.to_thread(_create_valid_bundle, tmp_path)
    entered, release = asyncio.Event(), asyncio.Event()

    class HeldStore(bundle_store.BundleStore):
        async def read_manifest(self, target):
            entered.set()
            await release.wait()
            return await super().read_manifest(target)

    store = HeldStore()
    service = BundleService(store=store, engine_version="0.6.24")
    models = ["qwen2.5-coder:3b"]
    pending = asyncio.create_task(service.validate(tmp_path, available_models=models))
    try:
        await asyncio.wait_for(entered.wait(), RESPONSIVENESS_SECONDS)
        service.store = None
        service.engine_version = "0.9.0"
        models.clear()
    finally:
        release.set()
        result = await asyncio.wait_for(pending, SETTLEMENT_SECONDS)
    assert result["ok"] is True
    assert result["engine_version_checked"] == "0.6.24"
    assert result["model_selection"]["selected_model"] == "qwen2.5-coder:3b"
