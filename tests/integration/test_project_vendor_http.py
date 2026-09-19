"""Real loopback HTTP proof for application-selected Gitea transport, not a live Gitea server."""
import asyncio
import json
import threading

import pytest

import orket.application.services.project_vendor_factory as factory_module
from orket.application.services.project_vendor_factory import create_project_vendor

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_factory_captures_configuration_and_reaches_selected_http_endpoint():
    observed = []
    settled = asyncio.Event()
    response = json.dumps([{"number": 7, "title": "Observed issue", "body": "Details", "state": "open"}]).encode()

    async def handle(reader, writer):
        try:
            request = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 3)
            observed.append(request.decode("ascii"))
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: "
                         + str(len(response)).encode() + b"\r\n\r\n" + response)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
            settled.set()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    config = {"url": f"http://127.0.0.1:{port}", "token": "fixture-token", "owner": "selected", "repo": "project"}
    vendor = None
    try:
        vendor = await create_project_vendor(settings={"vendor_type": "gitea", "gitea_config": config})
        config.update(url="http://invalid.example", token="changed", owner="changed", repo="changed")
        async with server:
            cards = await vendor.get_cards("42")
            await asyncio.wait_for(settled.wait(), 3)
        assert [(card.id, card.summary) for card in cards] == [("7", "Observed issue")]
        assert observed[0].startswith("GET /api/v1/repos/selected/project/issues?labels=42 HTTP/1.1\r\n")
        assert "authorization: token fixture-token\r\n" in observed[0].lower()
    finally:
        if vendor is not None:
            await vendor.close()
        server.close()
        await server.wait_closed()
    assert vendor._client.is_closed


async def _create(settings):
    return await create_project_vendor(settings=settings)


@pytest.mark.parametrize("stop", ["cancel", "timeout"])
async def test_interrupted_http_client_construction_stays_responsive_and_closes_client(monkeypatch, stop):
    entered, release = threading.Event(), threading.Event()
    original, made = factory_module.GiteaVendor, []

    def held(*args):
        entered.set()
        assert release.wait(5)
        client = original(*args)
        made.append(client)
        return client

    monkeypatch.setattr(factory_module, "GiteaVendor", held)
    settings = {"vendor_type": "gitea", "gitea_config": {
        "url": "http://127.0.0.1:1", "token": "fixture-token", "owner": "owner", "repo": "repo",
    }}
    # Independent release lets the synchronous counterexample terminate and close.
    watchdog = threading.Timer(3, release.set)
    watchdog.start()
    started = asyncio.get_running_loop().time()
    command = _create(settings)
    request = asyncio.create_task(asyncio.wait_for(command, 0.05) if stop == "timeout" else command)
    try:
        assert await asyncio.to_thread(entered.wait, 4)
        assert asyncio.get_running_loop().time() - started < 0.5
        settings["gitea_config"]["token"] = "changed"
        if stop == "cancel":
            request.cancel()
            await asyncio.sleep(0)
            request.cancel()
        await asyncio.sleep(0.15)
        assert not request.done()
        released = asyncio.get_running_loop().time()
        release.set()
        result, = await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), 3)
        assert asyncio.get_running_loop().time() - released < 3
        assert isinstance(result, asyncio.CancelledError if stop == "cancel" else TimeoutError)
        assert len(made) == 1 and made[0]._client.is_closed
        assert made[0].headers["Authorization"] == "token fixture-token"
    finally:
        release.set()
        watchdog.cancel()
        await asyncio.to_thread(watchdog.join)
        await asyncio.gather(request, return_exceptions=True)
        for client in made:
            await client.close()
