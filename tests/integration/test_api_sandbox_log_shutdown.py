"""Real TCP shutdown settles the entire ephemeral sandbox query lifetime."""
import asyncio
import threading
from contextlib import AsyncExitStack, nullcontext
from types import SimpleNamespace

import pytest

from orket.interfaces.api import create_api_app
from tests.integration.test_api_active_request_ownership import serving_api
from tests.integration.test_api_sandbox_log_ownership import install_pipeline_probe

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("stage", ["construction", "read", "close"])
@pytest.mark.parametrize("failure", [False, True])
async def test_sandbox_log_shutdown_settles_pipeline_and_native_work(tmp_path, monkeypatch, stage, failure):
    await asyncio.to_thread((tmp_path / "sandbox-log-input.txt").write_text, "owned", encoding="utf-8")
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(),
                            files=[], owners=[], cleanup=[], children=[], commands=[])
    app = create_api_app(project_root=tmp_path, environment={"ORKET_API_KEY": "bt0-local-test-key"})
    async with AsyncExitStack() as lifetime:
        lifetime.enter_context(pytest.raises(RuntimeError, match="teardown failed") if failure else nullcontext())
        client = await lifetime.enter_async_context(serving_api(app))
        context = app.state.api_runtime_context
        install_pipeline_probe(app, tmp_path, monkeypatch, state, stage, "worker_failure" if failure else "normal")
        request, closing = None, None
        timer = threading.Timer(.8, state.release.set)
        timer.start()
        try:
            request = asyncio.create_task(client.get("/v1/sandboxes/sandbox-test/logs"))
            assert await asyncio.to_thread(state.entered.wait, 5)
            assert (await asyncio.wait_for(client.get("/v1/system/heartbeat"), .5)).status_code == 200
            closing = asyncio.create_task(context.close())
            await asyncio.sleep(.08)
            assert not closing.done() and not state.finished.is_set()
            assert context.active_request_count == 1 and all(not owner._closed for owner in state.owners)
            if stage == "read":
                assert state.children and all(child.poll() is None for child in state.children)
            state.release.set()
            if failure:
                with pytest.raises(RuntimeError, match="teardown failed") as observed:
                    await asyncio.wait_for(closing, 5)
                assert isinstance(observed.value.__cause__, RuntimeError if stage == "read" else OSError)
            else:
                await asyncio.wait_for(closing, 5)
            assert (await asyncio.wait_for(request, 5)).status_code == (500 if failure else 503)
            assert all(owner._closed for owner in state.owners) and context.active_request_count == 0
        finally:
            state.release.set()
            timer.cancel()
            await asyncio.to_thread(timer.join, 5)
            await asyncio.gather(*(task for task in (request, closing) if task is not None), return_exceptions=True)
            assert await asyncio.to_thread(state.finished.wait, 5)
            for close in state.cleanup:
                await close()
        assert not timer.is_alive() and all(stream.closed for stream in state.files)
        assert all(child.returncode is not None and child.stdin.closed and child.stdout.closed for child in state.children)
