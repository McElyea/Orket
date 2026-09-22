"""Owned loopback HTTP observations with caller-supplied controlled JSON responses."""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager


@asynccontextmanager
async def observed_http_server(response_for_request, *, allow_disconnect=False, content_type="application/json",
                               ssl_context=None, request_headers=None, response_headers=()):
    requests, owners, completed, errors, disconnects = [], set(), set(), [], []

    async def respond(reader, writer):
        owner = asyncio.current_task()
        owners.add(owner)
        try:
            head = await reader.readuntil(b"\r\n\r\n")
            first, *headers = head.decode().split("\r\n")
            if request_headers is not None:
                request_headers.append({key.lower(): value.strip() for h in headers if ":" in h
                                        for key, value in [h.split(":", 1)]})
            length = next((int(h.split(":", 1)[1]) for h in headers if h.lower().startswith("content-length:")), 0)
            body = await reader.readexactly(length)
            request = (first, json.loads(body) if body else None)
            requests.append(request)
            response = await response_for_request(request)
            if response is None:
                # Interruption controls observe actual peer EOF instead of racing
                # a response against the cancelled client's socket shutdown.
                assert await asyncio.wait_for(reader.read(1), timeout=5) == b""
                return
            status, payload = response
            content = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            writer.write(f"HTTP/1.1 {status} Controlled\r\nContent-Type: {content_type}\r\n".encode() +
                         b"".join(f"{key}: {value}\r\n".encode() for key, value in response_headers) +
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

    server = await asyncio.start_server(respond, "127.0.0.1", 0, ssl=ssl_context,
                                       ssl_handshake_timeout=3 if ssl_context else None)
    try:
        scheme = "https" if ssl_context else "http"
        yield f"{scheme}://127.0.0.1:{server.sockets[0].getsockname()[1]}", requests
    finally:
        server.close()
        await asyncio.wait_for(server.wait_closed(), timeout=5)
        if owners or completed:
            await asyncio.wait_for(asyncio.gather(*(owners | completed)), timeout=5)
        assert not owners and not errors
        assert allow_disconnect or not disconnects, disconnects
