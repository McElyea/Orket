"""Layer: integration. Actual bounded streams and failed executable launch."""
from __future__ import annotations

import sys

import pytest

from orket.adapters.tools.registry import DEFAULT_BUILTIN_CONNECTOR_REGISTRY
from orket.application.services.outward_connector_service import OutwardConnectorService

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("stream,descriptor", [("stdout", 1), ("stderr", 2)])
# Layer: integration
async def test_stream_byte_count_is_raw_capture_not_replacement_text_size(tmp_path, stream, descriptor):
    service = OutwardConnectorService(connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY, workspace_root=tmp_path)
    event, result = await service.invoke_with_result("run_command", {"command": [sys.executable, "-c",
        f"import os; os.write({descriptor}, bytes([255,254,253]))"]})
    assert event["outcome"] == "success" and result[f"{stream}_preview"] == "\ufffd" * 3
    assert result[f"{stream}_bytes"] == event["result_summary"][f"{stream}_bytes"] == 3


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
# Layer: integration
async def test_output_limit_is_failed_capture_with_confirmed_cleanup(tmp_path, stream):
    service = OutwardConnectorService(connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY, workspace_root=tmp_path)
    event, result = await service.invoke_with_result("run_command", {"command": [sys.executable, "-c",
        f"import sys; sys.{stream}.buffer.write(b'x'*(5*1024*1024)); sys.{stream}.flush()"]})
    assert event["outcome"] == "failed" and result["error"] == "output_limit"
    assert result[f"{stream}_bytes"] == 4 * 1024 * 1024
    assert len(result[f"{stream}_preview"]) == 256
    assert result["process_lifetime"]["cleanup_confirmed"] is True
    assert result["process_lifetime"]["capture_complete"] is False
    assert event["result_summary"]["process_lifetime"] == result["process_lifetime"]


# Layer: integration
async def test_missing_executable_returns_observed_launch_failure(tmp_path):
    service = OutwardConnectorService(connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY, workspace_root=tmp_path)
    event = await service.invoke("run_command", {"command": [str(tmp_path / "absent-executable")]})
    assert event["outcome"] == "failed" and event["result_summary"]["error"] == "launch_failed"
    lifetime = event["result_summary"]["process_lifetime"]
    assert lifetime["cleanup_confirmed"] is True and lifetime["command_pid"] is None
    assert lifetime["diagnostics"]
