"""A real coordinator HTTP server with the existing five-second startup/teardown bounds."""
import asyncio
import socket
from contextlib import asynccontextmanager

import uvicorn


@asynccontextmanager
async def coordinator_server(app):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, lifespan="on", log_level="error"))
        serving = asyncio.create_task(server.serve(sockets=[listener]))

        async def wait_started():
            while not server.started:
                if serving.done():
                    await serving
                    raise AssertionError("HTTP server stopped before startup")
                await asyncio.sleep(0.01)

        try:
            await asyncio.wait_for(wait_started(), 5)
            yield f"http://127.0.0.1:{port}"
        finally:
            server.should_exit = True
            await asyncio.wait_for(serving, 5)
    assert serving.done()
