"""Actual native capture with bounded per-call overrides and unchanged default refusal."""
from __future__ import annotations

import asyncio
import sys

import pytest

from orket.application.services.command_process_supervisor import CommandProcessSupervisor


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", ["stdout", "stderr"])
@pytest.mark.parametrize("exceeds", [False, True])
# Layer: integration
async def test_owned_command_capture_uses_the_admitted_limit(tmp_path, stream, exceeds):
    size = (7 if exceeds else 5) * 1024 * 1024
    limit = 6 * 1024 * 1024
    owner = CommandProcessSupervisor(tmp_path, cancellation_event="verification_process_cancelled")
    result = await owner.run([sys.executable, "-c", f"import sys; sys.{stream}.buffer.write(b'x' * {size})"],
                              cwd=tmp_path, timeout_seconds=10, output_limit_bytes=limit)
    assert len(getattr(result, stream)) == (limit if exceeds else size)
    assert result.cleanup_confirmed and result.capture_complete is (not exceeds)
    assert result.reason == ("output_limit" if exceeds else "completed")
    if not exceeds:
        assert result.returncode == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [0, -1, True, 1.5, "4096", 64 * 1024 * 1024 + 1])
# Layer: integration
async def test_invalid_capture_limit_refuses_before_command_admission(tmp_path, limit):
    owner = CommandProcessSupervisor(tmp_path, cancellation_event="verification_process_cancelled")
    with pytest.raises(ValueError, match="E_COMMAND_OUTPUT_LIMIT_INVALID"):
        await owner.run([sys.executable, "-c", "from pathlib import Path; Path('effect').touch()"],
                         cwd=tmp_path, timeout_seconds=5, output_limit_bytes=limit)
    assert not await asyncio.to_thread((tmp_path / "effect").exists)
