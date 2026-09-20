"""Actual prompt commands admit authored roles without silently repairing invalid IDs."""
from __future__ import annotations

import asyncio
import json

import pytest

from tests.application.test_prompts_cli import _seed_assets
from tests.integration.test_runtime_entrypoints import child

pytestmark = [pytest.mark.end_to_end, pytest.mark.asyncio]


@pytest.mark.parametrize("command", ["resolve", "validate"])
@pytest.mark.parametrize("invalid", [False, True], ids=["absent_identity", "invalid_explicit_identity"])
async def test_prompt_cli_admits_authored_role_identity_without_source_rewrite(tmp_path, command, invalid):
    await asyncio.to_thread(_seed_assets, tmp_path)
    path = tmp_path / "model/core/roles/architect.json"
    payload = json.loads(await asyncio.to_thread(path.read_text, encoding="utf-8"))
    if invalid:
        payload["id"] = None
    else:
        del payload["id"]
    original = json.dumps(payload)
    await asyncio.to_thread(path.write_text, original, encoding="utf-8")
    arguments = ["-m", "orket.interfaces.prompts_cli", "--root", str(tmp_path), command]
    arguments += ["--role", "architect", "--dialect", "generic", "--include-prompt"] if command == "resolve" else ["--json"]
    code, output, error = await child(tmp_path, arguments)
    assert code == (1 if invalid else 0), output + error
    if invalid:
        assert "Input should be a valid string" in output + error
    elif command == "resolve":
        result = json.loads(output)
        assert result["metadata"]["prompt_id"] == "role.architect+dialect.generic"
        assert "Architect role." in result["prompt"]
    else:
        result, end = json.JSONDecoder().raw_decode(output)
        assert result["ok"] is True and result["error_count"] == 0
        assert output[end:].strip() == "Prompt assets valid."
    assert await asyncio.to_thread(path.read_text, encoding="utf-8") == original
