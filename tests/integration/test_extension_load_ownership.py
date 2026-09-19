"""Retain the real extension registration worker through caller interruption."""
import asyncio
import hashlib
import threading

import pytest

from orket.extensions.models import ExtensionRecord, _ExtensionManifestEntry
from orket.extensions.reproducibility import ReproducibilityEnforcer
from orket.extensions.workload_executor import WorkloadExecutor
from tests.integration.test_extension_module_origin import _source

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('stop', ['cancel', 'timeout'])
async def test_legacy_registration_worker_settles_before_interruption_returns(tmp_path, stop):
    """Layer: integration. Real module loading reaches a controlled registry, then drains."""
    module = 'owned_load_' + hashlib.sha256(str(tmp_path).encode()).hexdigest()[:12]
    await asyncio.to_thread(_source, tmp_path, module, 'selected')
    entered, release, settled = threading.Event(), threading.Event(), threading.Event()
    items = {}

    class Registry:
        def register_workload(self, item):
            entered.set()
            try:
                assert release.wait(10)
                items[item.workload_id] = item
            finally:
                settled.set()

        def workloads(self):
            return dict(items)

    executor = WorkloadExecutor(project_root=tmp_path, reproducibility=ReproducibilityEnforcer(tmp_path),
                                registry_factory=Registry)
    entry = _ExtensionManifestEntry('fixture', '1')
    extension = ExtensionRecord('owned', '1', 'fixture', '1', str(tmp_path), module, 'register', (entry,))
    operation = executor.run_legacy_workload(extension=extension, workload=entry, control_plane_workload_record={},
        input_config={}, workspace=tmp_path / 'workspace', department='core')
    request = asyncio.create_task(asyncio.wait_for(operation, 0.05) if stop == 'timeout' else operation)
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        started = asyncio.get_running_loop().time()
        await asyncio.to_thread((tmp_path / 'responsive').write_text, 'ready', encoding='utf-8')
        assert asyncio.get_running_loop().time() - started < 0.5
        if stop == 'cancel':
            request.cancel()
            await asyncio.sleep(0)
            request.cancel()
        await asyncio.sleep(0.1)
        assert not request.done() and not settled.is_set()
        release.set()
        result, = await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), 3)
        assert isinstance(result, asyncio.CancelledError if stop == 'cancel' else TimeoutError)
        assert settled.is_set() and items['fixture'].marker == 'selected'
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), 3)


@pytest.mark.parametrize('stop', ['cancel', 'timeout'])
async def test_sdk_source_validation_settles_before_interruption_returns(tmp_path, monkeypatch, stop):
    """Layer: integration. Controlled source validation drains before SDK child admission."""
    module = 'selected'
    await asyncio.to_thread(_source, tmp_path, module, 'selected')
    entered, release, settled = threading.Event(), threading.Event(), threading.Event()
    executor = WorkloadExecutor(project_root=tmp_path, reproducibility=ReproducibilityEnforcer(tmp_path),
                                registry_factory=lambda: None)
    original = executor.loader.validate_extension_imports

    def held(*args, **kwargs):
        entered.set()
        try:
            assert release.wait(10)
            return original(*args, **kwargs)
        finally:
            settled.set()

    monkeypatch.setattr(executor.loader, 'validate_extension_imports', held)
    entry = _ExtensionManifestEntry('fixture', '1', entrypoint='selected:Work', contract_style='sdk_v0')
    extension = ExtensionRecord('owned', '1', 'fixture', 'v0', str(tmp_path), '', '', (entry,), contract_style='sdk_v0')
    operation = executor.run_sdk_workload(extension=extension, workload=entry, control_plane_workload_record={},
        input_config={}, workspace=tmp_path / 'workspace', department='core')
    request = asyncio.create_task(asyncio.wait_for(operation, 0.05) if stop == 'timeout' else operation)
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        started = asyncio.get_running_loop().time()
        await asyncio.to_thread((tmp_path / 'responsive').write_text, 'ready', encoding='utf-8')
        assert asyncio.get_running_loop().time() - started < 0.5
        if stop == 'cancel':
            request.cancel()
            await asyncio.sleep(0)
            request.cancel()
        await asyncio.sleep(0.1)
        assert not request.done() and not settled.is_set()
        release.set()
        result, = await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), 3)
        assert isinstance(result, asyncio.CancelledError if stop == 'cancel' else TimeoutError)
        assert settled.is_set()
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), 3)
