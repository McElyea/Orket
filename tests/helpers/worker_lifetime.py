"""Real TCP/SQLite Worker fixture with explicit, bounded renewal-response holds."""
import asyncio
import threading
import time
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.execution.worker_client import Worker
from tests.helpers.coordinator import app_for
from tests.helpers.coordinator_server import coordinator_server


def _worker(rig, client):
    def response_hook(response):
        if response.request.url.path.endswith("/renew"):
            assert response.status_code == 200
            rig.entered.set()
            assert rig.release.wait(5), "release actual renewal HTTP response"
            if rig.renew_failure:
                raise OSError("renewal failed after real HTTP acceptance")

    def sleep(seconds):
        if threading.get_ident() == rig.parent and rig.work_failure:
            assert rig.entered.wait(5), "actual renewal accepted before work failure"
            rig.work_failed.set()
            raise ValueError("work failed during real renewal")
        time.sleep(seconds)

    client.event_hooks["response"].append(response_hook)
    worker = Worker(node_id="worker", base_url=str(client.base_url).rstrip("/"), client=client,
                    lease_duration=20, renew_interval=0.01, sleep_fn=sleep)
    original = worker._renew_loop

    def observe(card_id, stop):
        rig.thread, rig.stop = threading.current_thread(), stop
        try:
            return original(card_id, stop)
        finally:
            rig.finished.set()

    worker._renew_loop = observe
    return worker


@asynccontextmanager
async def worker_lifetime(root, *, work_failure=False, renew_failure=False):
    rig = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(),
                          work_failed=threading.Event(),
                          parent=None, thread=None, stop=None, task=None,
                          work_failure=work_failure, renew_failure=renew_failure)
    app = app_for(root)
    rig.owner = app.state.coordinator
    async with coordinator_server(app) as url:
        rig.url = url
        client = await asyncio.to_thread(httpx.Client, base_url=url, trust_env=False, timeout=2)
        rig.client, rig.worker = client, _worker(rig, client)
        try:
            claim = await run_owned_thread(lambda: rig.worker.claim("card"), label="fixture-worker-claim")
            assert claim.status_code == 200
            yield rig
        finally:
            rig.release.set()
            if rig.stop is not None:
                rig.stop.set()
            if rig.task is not None:
                await asyncio.wait_for(asyncio.gather(rig.task, return_exceptions=True), 5)
            if rig.thread is not None:
                await asyncio.to_thread(rig.thread.join, 5)
                assert not rig.thread.is_alive()
            await asyncio.to_thread(client.close)
    assert rig.owner.closed and client.is_closed


def start_work(rig, *, timeout=False):
    def invoke():
        rig.parent = threading.get_ident()
        return rig.worker.run_claimed_work("card", work_duration=0.15, completion_result={"worker": "worker"})

    async def run():
        operation = run_owned_thread(invoke, label="fixture-worker-work")
        return await asyncio.wait_for(operation, 0.1) if timeout else await operation

    rig.task = asyncio.create_task(run())
    return rig.task
