from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

from orket.adapters.tools.registry import (
    DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
    BuiltInConnectorMetadata,
    BuiltInConnectorRegistry,
)
from orket.application.services.outward_connector_service import (
    OutwardConnectorArgumentError,
    OutwardConnectorService,
)


class _RecordingExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def invoke(self, connector_name: str, args: dict[str, Any], *, timeout_seconds: float) -> dict[str, Any]:
        self.calls.append((connector_name, args))
        return {"ok": True}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_connector_service_rejects_invalid_args_before_invocation(tmp_path: Path) -> None:
    """Layer: unit. Verifies schema validation fails before connector invocation."""
    executor = _RecordingExecutor()
    service = OutwardConnectorService(
        connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
        workspace_root=tmp_path,
        executor=executor,  # type: ignore[arg-type]
    )

    with pytest.raises(OutwardConnectorArgumentError) as exc:
        await service.invoke("write_file", {"path": "missing-content.txt"})

    assert exc.value.errors == [{"field": "content", "reason": "required"}]
    assert executor.calls == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_connector_service_invokes_filesystem_connectors_and_returns_ledger_shape(tmp_path: Path) -> None:
    """Layer: integration. Verifies built-in file connectors return the real invocation ledger field shape."""
    service = OutwardConnectorService(
        connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
        workspace_root=tmp_path,
    )

    created = await service.invoke("create_directory", {"path": "nested"})
    written = await service.invoke("write_file", {"path": "nested/demo.txt", "content": "hello"})
    read = await service.invoke("read_file", {"path": "nested/demo.txt"})
    deleted = await service.invoke("delete_file", {"path": "nested/demo.txt"})

    assert set(created) == {"connector_name", "args_hash", "result_summary", "duration_ms", "outcome"}
    assert created["outcome"] == "success"
    assert written["outcome"] == "success"
    assert read["outcome"] == "success"
    assert read["result_summary"]["content_bytes"] == len("hello")
    assert deleted["outcome"] == "success"
    assert (tmp_path / "nested" / "demo.txt").exists() is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_connector_service_rejects_path_traversal_before_file_effect(tmp_path: Path) -> None:
    """Layer: integration. Verifies workspace path containment rejects traversal without file creation."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    service = OutwardConnectorService(
        connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
        workspace_root=workspace,
    )

    result = await service.invoke("write_file", {"path": "../escape.txt", "content": "escape"})

    assert result["outcome"] == "failed"
    assert (tmp_path / "escape.txt").exists() is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_connector_service_rejects_non_allowlisted_http_before_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Layer: integration. Verifies HTTP allowlist rejection happens before constructing a client."""

    class _BlockedClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise AssertionError("network client should not be constructed")

    monkeypatch.setattr("orket.adapters.tools.builtin_connectors.httpx.AsyncClient", _BlockedClient)
    service = OutwardConnectorService(
        connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
        workspace_root=tmp_path,
    )

    result = await service.invoke("http_get", {"url": "https://example.com/resource"})

    assert result["outcome"] == "failed"
    assert result["result_summary"]["error"] == "HTTP connector allowlist is required"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_connector_service_http_allowlist_admits_matching_host(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Layer: integration. Verifies allowlisted HTTP connectors can use the async HTTP adapter."""

    class _Client:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "_Client":
            return self

        async def __aexit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> None:
            return None

        async def get(self, url: str) -> httpx.Response:
            assert url == "https://example.com/resource"
            return httpx.Response(200, text="ok")

    monkeypatch.setattr("orket.adapters.tools.builtin_connectors.httpx.AsyncClient", _Client)
    service = OutwardConnectorService(
        connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
        workspace_root=tmp_path,
        http_allowlist=("example.com",),
    )

    result = await service.invoke("http_get", {"url": "https://example.com/resource"})

    assert result["outcome"] == "success"
    assert result["result_summary"]["status_code"] == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_connector_service_enforces_runtime_timeout(tmp_path: Path) -> None:
    """Layer: integration. Verifies runtime timeout produces the canonical timeout outcome."""

    class _SlowExecutor:
        async def invoke(self, connector_name: str, args: dict[str, Any], *, timeout_seconds: float) -> dict[str, Any]:
            await asyncio.sleep(1)
            return {"ok": True}

    registry = BuiltInConnectorRegistry(
        [
            BuiltInConnectorMetadata(
                name="slow",
                description="Slow connector",
                args_schema={"type": "object", "additionalProperties": False},
                risk_level="read",
                timeout_seconds=0.01,
            )
        ]
    )
    service = OutwardConnectorService(
        connector_registry=registry,
        workspace_root=tmp_path,
        executor=_SlowExecutor(),  # type: ignore[arg-type]
    )

    result = await service.invoke("slow", {})

    assert result["outcome"] == "timeout"
    assert result["result_summary"]["error"] == "timeout"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_connector_service_run_command_uses_exec_without_shell(tmp_path: Path) -> None:
    """Layer: integration. Verifies run_command executes an argv payload and returns summary fields."""
    service = OutwardConnectorService(
        connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
        workspace_root=tmp_path,
    )

    result = await service.invoke("run_command", {"command": [sys.executable, "-c", "print('ok')"]})

    assert result["outcome"] == "success"
    assert result["result_summary"]["returncode"] == 0
    assert result["result_summary"]["stdout_bytes"] > 0
