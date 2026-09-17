"""Real child output must not become stronger evidence after lossy capture."""
from __future__ import annotations

import sys

import pytest

from orket.application.services.runtime_verifier import RuntimeVerifier

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
@pytest.mark.parametrize("output,reason", [
    (b'{"answer":42}' + b' ' * 2000 + b'not-json', "stdout_capture_incomplete"),
    (b'{"answer":"' + b'a' * 2100 + b'"}', "stdout_capture_incomplete"),
    (b'{"answer":"\xff"}', "stdout_encoding_invalid"),
], ids=["hidden-invalid-suffix", "oversized-valid-json", "invalid-utf8"])
# Layer: integration
async def test_lossy_output_cannot_pass_runtime_json_verification(tmp_path, output, reason):
    verifier = RuntimeVerifier(tmp_path, issue_params={"runtime_verifier": {
        "commands": [[sys.executable, "-c", f"import sys; sys.stdout.buffer.write({output!r})"]],
        "expect_json_stdout": True,
    }})
    result = await verifier.verify()
    assert result.ok is False
    assert result.command_results[0]["returncode"] == 0
    assert result.command_results[0]["stdout_contract_ok"] is False
    assert result.command_results[0]["failure_class"] == reason
    assert result.failure_breakdown[reason] == 1


@pytest.mark.asyncio
# Layer: integration
async def test_complete_utf8_output_preserves_json_verification_and_exposes_capture_metadata(tmp_path):
    verifier = RuntimeVerifier(tmp_path, issue_params={"runtime_verifier": {
        "commands": [[sys.executable, "-c", 'import sys; sys.stdout.buffer.write(b\'{"answer":42}\'); sys.stderr.write("x" * 2100)']],
        "expect_json_stdout": True,
        "json_assertions": [{"path": "answer", "op": "eq", "value": 42}],
    }})
    result = await verifier.verify()
    assert result.ok is True
    command = result.command_results[0]
    assert command["stdout_contract_ok"] is True
    assert command["stdout_truncated"] is False
    assert command["stdout_encoding_valid"] is True
    assert command["stderr_truncated"] is True
    assert len(command["stderr"]) < 2100
