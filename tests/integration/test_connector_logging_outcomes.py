"""Layer: integration. Actual trust failure, native log effects and primary outcome."""
import asyncio
import json
import logging
import ssl
import threading
from pathlib import Path

import pytest

import orket.logging as logging_module
from orket.application.services.outward_connector_service import OutwardConnectorService
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.helpers.observed_http_server import observed_http_server
from tests.integration.test_short_http_ownership import clean_network

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def observe_trust_failure(monkeypatch, missing):
    monkeypatch.setenv('SSL_CERT_FILE', str(missing))
    original, errors = ssl.SSLContext.load_verify_locations, []

    def observe(context, *args, **options):
        try:
            return original(context, *args, **options)
        except FileNotFoundError as exc:
            errors.append(exc)
            raise

    monkeypatch.setattr(ssl.SSLContext, 'load_verify_locations', observe)
    return errors


def hold_write(monkeypatch, workspace, fail):
    original = logging_module._append_line_sync
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    threads = []

    def write(path, line):
        if path != workspace / 'orket.log':
            return original(path, line)
        threads.append(threading.get_ident())
        entered.set()
        try:
            assert release.wait(.8), 'Native logging owner did not release'
            original(path, line)
            if fail:
                raise OSError('controlled failure after physical log write')
        finally:
            finished.set()

    monkeypatch.setattr(logging_module, '_append_line_sync', write)
    return entered, release, finished, threads


@pytest.mark.parametrize('primary', ['cancel', 'trust-error'])
@pytest.mark.parametrize('stop', ['repeated', 'timeout'])
@pytest.mark.parametrize('fail_write', [False, True])
async def test_log_attempt_retains_primary_outcome(tmp_path, monkeypatch, record_property, caplog, primary, stop, fail_write):
    clean_network(monkeypatch)
    service = await OutwardConnectorService.for_workspace(tmp_path, http_allowlist=('127.0.0.1',))
    errors = observe_trust_failure(monkeypatch, tmp_path / 'absent.pem') if primary == 'trust-error' else []
    entered, release, finished, threads = hold_write(monkeypatch, tmp_path, fail_write)
    request_entered, server_release, deadline = asyncio.Event(), asyncio.Event(), asyncio.timeout(None)
    outcomes = []

    async def response(_request):
        request_entered.set()
        await asyncio.wait_for(server_release.wait(), 5)
        return None

    async with observed_http_server(response, allow_disconnect=True) as server:
        async def operation():
            try:
                async with deadline:
                    return await service.invoke_with_result('http_get', {'url': server[0]})
            except (asyncio.CancelledError, FileNotFoundError, TimeoutError) as exc:
                outcomes.append(exc)
                raise

        task = asyncio.create_task(operation())
        try:
            if primary == 'cancel':
                await asyncio.wait_for(request_entered.wait(), 5)
                task.cancel()
            assert await asyncio.to_thread(entered.wait, 5)
            await responsive_sqlite(tmp_path / 'response.sqlite3', record_property)
            if stop == 'timeout':
                deadline.reschedule(asyncio.get_running_loop().time() + .01)
            else:
                task.cancel()
                await asyncio.sleep(0)
                task.cancel()
            await asyncio.sleep(.03)
            assert not task.done() and not finished.is_set() and threads[0] != threading.get_ident()
            release.set()
            with pytest.raises(FileNotFoundError if primary == 'trust-error' else asyncio.CancelledError):
                await asyncio.wait_for(asyncio.shield(task), 5)
            assert outcomes[0] is errors[0] if errors else isinstance(outcomes[0], asyncio.CancelledError)
            assert finished.is_set() and len(server[1]) == (primary == 'cancel')
            records = json.loads(await asyncio.to_thread((tmp_path / 'orket.log').read_text, encoding='utf-8'))
            assert records['event'] == 'outward_connector_interrupted'
            assert records['data']['observation'] == ('cancelled' if primary == 'cancel' else 'unresolved')
            assert ('Unable to record interrupted connector timing' in caplog.text) is fail_write
        finally:
            release.set()
            server_release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)


async def test_failed_logging_and_diagnostic_sink_cannot_hide_primary(tmp_path, monkeypatch, record_property):
    clean_network(monkeypatch)
    service = await OutwardConnectorService.for_workspace(tmp_path, http_allowlist=('127.0.0.1',))
    errors = observe_trust_failure(monkeypatch, tmp_path / 'absent.pem')
    entered, release = threading.Event(), threading.Event()
    observed = []

    class BrokenSink(logging.Handler):
        def emit(self, record):
            if record.getMessage() == 'outward_connector_interrupted' or record.getMessage().startswith('Unable to record'):
                observed.append((record.name, threading.get_ident()))
                entered.set()
                assert release.wait(.8), 'Native diagnostic sink did not release'
                raise OSError('controlled broken diagnostic sink')

    logger, sink = logging.getLogger('orket'), BrokenSink()
    logger.addHandler(sink)
    task = asyncio.create_task(service.invoke_with_result('http_get', {'url': 'http://127.0.0.1:1'}))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        await responsive_sqlite(tmp_path / 'response.sqlite3', record_property)
        task.cancel()
        await asyncio.sleep(.01)
        assert not task.done()
        release.set()
        with pytest.raises(FileNotFoundError) as outcome:
            await asyncio.wait_for(asyncio.shield(task), 5)
        assert outcome.value is errors[0]
        assert len(observed) == 2 and all(t != threading.get_ident() for _, t in observed)
        assert any('telemetry' in note and 'OSError' in note for note in outcome.value.__notes__)
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        logger.removeHandler(sink)


async def test_interruption_log_keeps_invocation_workspace(tmp_path, monkeypatch):
    clean_network(monkeypatch)
    await asyncio.to_thread((tmp_path / 'first').mkdir)
    await asyncio.to_thread((tmp_path / 'second').mkdir)
    monkeypatch.chdir(tmp_path / 'first')
    service = await OutwardConnectorService.for_workspace(Path('workspace'), http_allowlist=('127.0.0.1',))
    service.workspace_root = Path('workspace')
    entered, release = asyncio.Event(), asyncio.Event()

    async def response(_request):
        entered.set()
        await asyncio.wait_for(release.wait(), 5)
        return None

    async with observed_http_server(response, allow_disconnect=True) as server:
        task = asyncio.create_task(service.invoke_with_result('http_get', {'url': server[0]}))
        try:
            await asyncio.wait_for(entered.wait(), 5)
            monkeypatch.chdir(tmp_path / 'second')
            service.workspace_root = tmp_path / 'changed'
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(asyncio.shield(task), 5)
            assert await asyncio.to_thread((tmp_path / 'first/workspace/orket.log').exists)
            assert not await asyncio.to_thread((tmp_path / 'second/workspace').exists)
            assert not await asyncio.to_thread((tmp_path / 'changed').exists)
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)


async def test_caller_timeout_retains_log_until_physical_write(tmp_path, monkeypatch, record_property):
    clean_network(monkeypatch)
    service = await OutwardConnectorService.for_workspace(tmp_path, http_allowlist=('127.0.0.1',))
    entered, release, finished, threads = hold_write(monkeypatch, tmp_path, False)
    request_entered, server_release = asyncio.Event(), asyncio.Event()
    deadline = asyncio.timeout(None)

    async def response(_request):
        request_entered.set()
        await asyncio.wait_for(server_release.wait(), 5)
        return None

    async with observed_http_server(response, allow_disconnect=True) as server:
        async def operation():
            async with deadline:
                return await service.invoke_with_result('http_get', {'url': server[0]})

        task = asyncio.create_task(operation())
        try:
            await asyncio.wait_for(request_entered.wait(), 5)
            deadline.reschedule(asyncio.get_running_loop().time() + .01)
            assert await asyncio.to_thread(entered.wait, 5)
            await responsive_sqlite(tmp_path / 'response.sqlite3', record_property)
            assert not task.done() and not finished.is_set() and threads[0] != threading.get_ident()
            release.set()
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(asyncio.shield(task), 5)
            assert finished.is_set() and await asyncio.to_thread((tmp_path / 'orket.log').exists)
        finally:
            release.set()
            server_release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
