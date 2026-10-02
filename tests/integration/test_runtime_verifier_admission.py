"""Public verification against real files and owned children; no deployment claim."""
import asyncio
import json
import sys
from copy import deepcopy
from types import SimpleNamespace

import pytest

from orket.application.services.runtime_verifier import RuntimeVerifier

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _command(source):
    return [sys.executable, "-c", source]


async def _verify(root, *, commands, assertions=None, rules=None, **options):
    contract = dict(commands=commands, json_assertions=assertions or [])
    verifier = RuntimeVerifier(root, organization=SimpleNamespace(process_rules=rules or {}),
        issue_params={"runtime_verifier": contract}, **options)
    before = deepcopy(contract)
    result = await verifier.verify()
    assert contract == before
    return result


async def test_stdout_assertions_accept_supported_containers_and_numeric_comparisons(tmp_path):
    payload = {"text": "native output", "items": [2, {"answer": 3}], "value": "4"}
    assertions = [
        {"path": "text", "op": "contains", "value": "output"},
        {"path": "items", "op": "contains", "value": 2},
        {"path": "items", "op": "len_gte", "value": "2"},
        {"path": "items[1].answer", "op": "eq", "value": 3},
        {"path": "value", "op": "ne", "value": 4},
        *[{"path": "value", "op": op, "value": value}
          for op, value in [("gt", 3), ("gte", 4), ("lt", 5), ("lte", 4)]],
    ]
    result = await _verify(tmp_path, commands=[_command(f"print({json.dumps(payload)!r})")], assertions=assertions)
    assert result.ok and result.failure_breakdown == {} and result.errors == []
    command, = result.command_results
    assert command["stdout_json"] == payload and command["stdout_contract_ok"] is True
    assert command["process_lifetime"]["cleanup_confirmed"] is True


async def test_stdout_refusals_keep_each_assertion_diagnostic_despite_successful_exit(tmp_path):
    assertions = [{}, {"path": "absent", "op": "eq"},
        *[{"path": path, "op": "eq"} for path in ["items[bad]", "items[-1]", "items[2]", "value.child"]],
        {"path": "value", "op": "unknown"},
        *[{"path": path, "op": op, "value": expected} for path, op, expected in [
            ("value", "contains", 2), ("value", "len_gte", 1), ("items", "len_gte", "invalid"),
            ("text", "gt", 1), ("value", "lte", "invalid"), ("value", "gte", 3),
        ]],
    ]
    result = await _verify(tmp_path,
        commands=[_command('print(\'{"items":[1],"value":2,"text":"word"}\')')], assertions=assertions)
    assert not result.ok and result.failure_breakdown == {"stdout_assertion_failed": 1}
    assert len(result.errors) == len(assertions)
    assert result.errors[0] == "runtime stdout assertion missing path or op"
    assert result.errors[1:6] == [f"runtime stdout assertion path missing: {path}"
                                for path in ["absent", "items[bad]", "items[-1]", "items[2]", "value.child"]]
    assert "unknown assertion op" in result.errors[6]
    command, = result.command_results
    assert command["returncode"] == 0 and command["outcome"] == "fail"
    assert command["stdout_assertion_failures"] == result.errors
    assert result.guard_contract.result == "fail" and len(result.guard_contract.violations) == len(assertions)


@pytest.mark.parametrize("command", [
    {"argv": []}, {"argv": [" "]}, {"argv": ["python", 3]}, {"argv": ["python", "bad\x00value"]},
    {"argv": ["python", "-c", "pass"], "cwd": "missing"}, {"argv": None},
])
async def test_invalid_commands_refuse_before_any_following_command(tmp_path, command):
    result = await _verify(tmp_path, commands=[command,
        _command("from pathlib import Path; Path('unauthorized.txt').write_text('bad')")])
    assert not result.ok and result.failure_breakdown == {"command_failed": 1}
    refused, = result.command_results
    assert refused["returncode"] == 126 and refused["outcome"] == "fail"
    assert "process_lifetime" not in refused
    assert not await asyncio.to_thread((tmp_path / "unauthorized.txt").exists)


async def test_stdout_contract_without_commands_cannot_pass(tmp_path):
    result = await _verify(tmp_path, commands=[], assertions=[{"path": "value", "op": "eq", "value": 1}],
        rules={"runtime_verifier_commands": []})
    assert not result.ok and result.command_results == []
    assert result.failure_breakdown == {"stdout_contract_missing": 1}
    assert result.errors == ["runtime stdout contract requested but no runtime commands were executed"]


@pytest.mark.parametrize("code,failure", [(137, "oom_killed"), (124, "timeout"), (126, "missing_runtime")])
async def test_completed_nonzero_children_retain_exit_class_and_empty_output_summary(tmp_path, code, failure):
    result = await _verify(tmp_path, commands=[_command(f"import sys; sys.exit({code})")],
        assertions=[{"path": "value", "op": "eq", "value": 1}])
    assert not result.ok and result.failure_breakdown == {failure: 1}
    command, = result.command_results
    assert command["returncode"] == code and command["process_lifetime"]["reason"] == "completed"
    assert command["process_lifetime"]["cleanup_confirmed"] is True
    assert "stdout_contract_ok" not in command
    assert result.errors == [f"runtime command failed [{failure}] cwd=.: command exited non-zero with no captured output"]


@pytest.mark.parametrize("dependencies,profile", [(["package.json"], "node"),
    (["package.json", "requirements.txt"], "polyglot")])
async def test_native_dependency_files_select_profile_policy(tmp_path, dependencies, profile):
    root = tmp_path / "agent_output/dependencies"
    await asyncio.to_thread(root.mkdir, parents=True)
    for name in dependencies:
        await asyncio.to_thread((root / name).write_text, "{}" if name.endswith("json") else "", encoding="utf-8")
    rules = {"runtime_verifier_commands_by_profile": {profile: [None, _command(f"print({profile!r})")]},
             "runtime_verifier_timeout_sec": "invalid"}
    result = await _verify(tmp_path, commands=[], rules=rules)
    assert result.ok and result.checked_files == []
    command, = result.command_results
    assert command["stdout"].strip() == profile and command["policy_source"] == f"profile_policy:{profile}"


@pytest.mark.parametrize("artifact", [{"kind": "app"}, {"kind": "app", "entrypoint_path": "main.js"}])
async def test_nonpython_or_missing_entrypoint_does_not_authorize_default_execution(tmp_path, artifact):
    result = await _verify(tmp_path, commands=[], rules={"project_surface_profile": "api_vue"},
        artifact_contract=artifact)
    assert result.ok and result.command_results == [] and result.overall_evidence_class == "not_evaluated"


async def test_deployment_defaults_report_files_without_claiming_runtime_deployment(tmp_path):
    rules = {"runtime_verifier_commands": [], "runtime_verifier_require_deployment_files": True,
             "deployment_planner_required_files": {" ": "ignored"}, "project_surface_profile": "api_vue"}
    missing = await _verify(tmp_path, commands=[], rules=rules)
    expected = ["agent_output/deployment/Dockerfile", "agent_output/deployment/docker-compose.yml"]
    assert missing.failure_breakdown == {"deployment_missing": 1}
    assert missing.errors == ["missing deployment artifacts: " + ", ".join(expected)]
    for name in expected:
        path = tmp_path / name
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_text, "fixture only", encoding="utf-8")
    retained = await _verify(tmp_path, commands=[], rules=rules)
    assert retained.ok and retained.command_results == []
    assert retained.overall_evidence_class == "not_evaluated"
