"""Owned receiver for disposable Gitea delivery acceptance, with captured wire bytes."""

import asyncio
import socket
from contextlib import asynccontextmanager

import uvicorn


class CaptureDelivery:
    def __init__(self, app):
        self.app = app
        self.deliveries = asyncio.Queue()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] != "/webhook/gitea":
            return await self.app(scope, receive, send)
        body, reply, status = bytearray(), bytearray(), None

        async def observed_receive():
            message = await receive()
            if message["type"] == "http.request":
                body.extend(message.get("body", b""))
            return message

        async def observed_send(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            if message["type"] == "http.response.body":
                reply.extend(message.get("body", b""))
            await send(message)

        await self.app(scope, observed_receive, observed_send)
        await self.deliveries.put(
            {
                "headers": {key.decode(): value.decode() for key, value in scope["headers"]},
                "body": bytes(body).decode(),
                "response": bytes(reply).decode(),
                "status": status,
            }
        )


@asynccontextmanager
async def webhook_listener(app):
    captured = CaptureDelivery(app)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    address = listener.getsockname()
    server = uvicorn.Server(uvicorn.Config(captured, log_level="warning", lifespan="on"))
    task = asyncio.create_task(server.serve(sockets=[listener]))
    try:
        async with asyncio.timeout(10):
            while not server.started:
                if task.done():
                    task.result()
                    raise RuntimeError("Owned webhook listener stopped before readiness")
                await asyncio.sleep(0.02)
        yield captured, address
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, 15)
        listener.close()
        assert app.state.webhook_runtime.closed and app.state.webhook_runtime.client.is_closed
