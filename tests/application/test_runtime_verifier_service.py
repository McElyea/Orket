from __future__ import annotations

from pathlib import Path

import pytest

from orket.application.services.runtime_verifier import RuntimeVerifier


@pytest.mark.asyncio
async def test_runtime_verifier_passes_valid_python(tmp_path: Path):
    agent_output = tmp_path / "agent_output"
    agent_output.mkdir(parents=True, exist_ok=True)
    (agent_output / "main.py").write_text("print('ok')\n", encoding="utf-8")

    result = await RuntimeVerifier(tmp_path).verify()

    assert result.ok is True
    assert "agent_output/main.py" in result.checked_files
    assert result.errors == []


@pytest.mark.asyncio
async def test_runtime_verifier_fails_invalid_python(tmp_path: Path):
    agent_output = tmp_path / "agent_output"
    agent_output.mkdir(parents=True, exist_ok=True)
    (agent_output / "main.py").write_text("def broken(:\n    pass\n", encoding="utf-8")

    result = await RuntimeVerifier(tmp_path).verify()

    assert result.ok is False
    assert "agent_output/main.py" in result.checked_files
    assert len(result.errors) >= 1

