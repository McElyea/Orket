"""Owned loopback HTTP observations with caller-supplied controlled JSON responses."""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager


@asynccontextmanager
async def observed_http_server(response_for_request, *, allow_disconnect=False, content_type="application/json"):
    requests, owners, completed, errors, disconnects = [], set(), set(), [], []

    async def respond(reader, writer):
        owner = asyncio.current_task()
        owners.add(owner)
        try:
            head = await reader.readuntil(b"\r\n\r\n")
            first, *headers = head.decode().split("\r\n")
            length = next((int(h.split(":", 1)[1]) for h in headers if h.lower().startswith("content-length:")), 0)
            body = await reader.readexactly(length)
            request = (first, json.loads(body) if body else None)
            requests.append(request)
            status, payload = await response_for_request(request)
            content = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            writer.write(f"HTTP/1.1 {status} Controlled\r\nContent-Type: {content_type}\r\n".encode() +
                         f"Content-Length: {len(content)}\r\nConnection: close\r\n\r\n".encode() + content)
            await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError) as exc:
            disconnects.append(repr(exc))
        except ValueError as exc:
            errors.append(repr(exc))
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError as exc:
                disconnects.append(repr(exc))
            owners.remove(owner)
            completed.add(owner)

    server = await asyncio.start_server(respond, "127.0.0.1", 0)
    try:
        yield f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}", requests
    finally:
        server.close()
        await server.wait_closed()
        if owners or completed:
            await asyncio.wait_for(asyncio.gather(*(owners | completed)), timeout=5)
        assert not owners and not errors
        assert allow_disconnect or not disconnects, disconnects
