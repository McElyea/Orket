"""Real default-policy lookup in a fresh interpreter and a foreign working directory."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
@pytest.mark.parametrize("foreign_policy", ["absent", "poisoned"])
def test_default_policy_is_independent_of_cwd(tmp_path, foreign_policy):
    from orket.kernel.v1 import validator

    if foreign_policy == "poisoned":
        target = tmp_path / "model/core/contracts/kernel_capability_policy_v1.json"
        target.parent.mkdir(parents=True)
        target.write_text(
            json.dumps(
                {
                    "policy_source": "foreign-poison",
                    "policy_version": "wrong",
                    "default_permissions": ["foreign.execute"],
                    "role_task_permissions": {},
                }
            ),
            encoding="utf-8",
        )
    script = """
import json
import sys
sys.path.insert(0, sys.argv[1])
from orket.kernel.v1 import validator
from orket.kernel.v1.api import resolve_capability, authorize_tool_call
resolved = resolve_capability({
    'contract_version': 'kernel_api/v1', 'role': 'coder', 'task': 'edit'})
denied = authorize_tool_call({
    'contract_version': 'kernel_api/v1', 'context': {'role': 'coder', 'task': 'edit'},
    'tool_request': {'action': 'foreign.execute'}})
print(json.dumps({'resolved': resolved, 'denied': denied, 'origin': validator.__file__}))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", script, str(Path(validator.__file__).parents[3])],
        cwd=tmp_path,
        env=dict(os.environ, ORKET_DISABLE_SANDBOX="1"),
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    value = json.loads(result.stdout)
    assert Path(value["origin"]).resolve() == Path(validator.__file__).resolve()
    assert value["resolved"]["capability_plan"]["permissions"] == ["file.read", "file.write", "tool.call"]
    assert value["denied"]["decision"]["result"] == "DENY"
    assert value["denied"]["decision"]["reason_code"] == "E_CAPABILITY_DENIED"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_implicit_policy_read_refuses_running_event_loop():
    from orket.kernel.v1.api import resolve_capability

    with pytest.raises(RuntimeError, match="E_KERNEL_POLICY_REQUIRES_ASYNC_OWNER"):
        resolve_capability({"contract_version": "kernel_api/v1", "role": "coder", "task": "edit"})
