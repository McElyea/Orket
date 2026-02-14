from __future__ import annotations

from pathlib import Path
import sys

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
    assert result.command_results == []


@pytest.mark.asyncio
async def test_runtime_verifier_fails_invalid_python(tmp_path: Path):
    agent_output = tmp_path / "agent_output"
    agent_output.mkdir(parents=True, exist_ok=True)
    (agent_output / "main.py").write_text("def broken(:\n    pass\n", encoding="utf-8")

    result = await RuntimeVerifier(tmp_path).verify()

    assert result.ok is False
    assert "agent_output/main.py" in result.checked_files
    assert len(result.errors) >= 1


@pytest.mark.asyncio
async def test_runtime_verifier_runs_policy_commands(tmp_path: Path):
    agent_output = tmp_path / "agent_output"
    agent_output.mkdir(parents=True, exist_ok=True)
    (agent_output / "main.py").write_text("print('ok')\n", encoding="utf-8")

    org = type("Org", (), {"process_rules": {"runtime_verifier_commands": [[sys.executable, "-c", "print('ok')"]]}})
    result = await RuntimeVerifier(tmp_path, organization=org).verify()

    assert result.ok is True
    assert len(result.command_results) == 1
    assert result.command_results[0]["returncode"] == 0


@pytest.mark.asyncio
async def test_runtime_verifier_fails_on_runtime_command_error(tmp_path: Path):
    agent_output = tmp_path / "agent_output"
    agent_output.mkdir(parents=True, exist_ok=True)
    (agent_output / "main.py").write_text("print('ok')\n", encoding="utf-8")

    org = type("Org", (), {"process_rules": {"runtime_verifier_commands": [[sys.executable, "-c", "import sys; sys.exit(3)"]]}})
    result = await RuntimeVerifier(tmp_path, organization=org).verify()

    assert result.ok is False
    assert len(result.errors) >= 1
    assert result.command_results[0]["returncode"] == 3


@pytest.mark.asyncio
async def test_runtime_verifier_can_require_deployment_files(tmp_path: Path):
    agent_output = tmp_path / "agent_output"
    agent_output.mkdir(parents=True, exist_ok=True)
    (agent_output / "main.py").write_text("print('ok')\n", encoding="utf-8")

    org = type(
        "Org",
        (),
        {
            "process_rules": {
                "runtime_verifier_require_deployment_files": True,
                "runtime_verifier_required_deployment_files": [
                    "agent_output/deployment/Dockerfile",
                ],
            }
        },
    )
    result = await RuntimeVerifier(tmp_path, organization=org).verify()

    assert result.ok is False
    assert any("missing deployment artifacts" in err for err in result.errors)
