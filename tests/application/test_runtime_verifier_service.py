from __future__ import annotations

from pathlib import Path
import sys

import pytest

from orket.application.services.runtime_verifier import RuntimeVerifier


@pytest.mark.asyncio
async def test_runtime_verifier_passes_valid_python(tmp_path: Path):
    """Layer: contract. Verifies the builtin python profile command plan executes a real verifier command."""
    agent_output = tmp_path / "agent_output"
    agent_output.mkdir(parents=True, exist_ok=True)
    (agent_output / "main.py").write_text("print('ok')\n", encoding="utf-8")

    result = await RuntimeVerifier(tmp_path).verify()

    assert result.ok is True
    assert "agent_output/main.py" in result.checked_files
    assert result.errors == []
    assert len(result.command_results) == 1
    assert result.command_results[0]["returncode"] == 0
    assert result.command_results[0]["policy_source"] == "profile_default:python"
    assert result.failure_breakdown == {}
    assert result.guard_contract.result == "pass"
    assert result.guard_contract.terminal_failure is False
    assert result.guard_contract.terminal_reason is None
    assert result.guard_contract.violations == []


@pytest.mark.asyncio
async def test_runtime_verifier_fails_invalid_python(tmp_path: Path):
    """Layer: contract. Verifies syntax failures remain explicit even when builtin verifier commands also run."""
    agent_output = tmp_path / "agent_output"
    agent_output.mkdir(parents=True, exist_ok=True)
    (agent_output / "main.py").write_text("def broken(:\n    pass\n", encoding="utf-8")

    result = await RuntimeVerifier(tmp_path).verify()

    assert result.ok is False
    assert "agent_output/main.py" in result.checked_files
    assert len(result.errors) >= 1
    assert len(result.command_results) == 1
    assert result.guard_contract.result == "fail"
    assert result.guard_contract.severity == "strict"
    assert result.guard_contract.terminal_failure is False
    assert result.guard_contract.terminal_reason is None
    assert result.guard_contract.violations[0].rule_id == "RUNTIME_VERIFIER.FAIL"
    assert result.guard_contract.violations[0].evidence


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
    assert result.command_results[0]["policy_source"] == "policy_override"


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
    assert result.command_results[0]["failure_class"] == "command_failed"
    assert result.failure_breakdown.get("command_failed", 0) >= 1


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
    assert result.failure_breakdown.get("deployment_missing", 0) >= 1


@pytest.mark.asyncio
async def test_runtime_verifier_uses_deployment_planner_required_files_when_present(tmp_path: Path):
    agent_output = tmp_path / "agent_output"
    agent_output.mkdir(parents=True, exist_ok=True)
    (agent_output / "main.py").write_text("print('ok')\n", encoding="utf-8")

    org = type(
        "Org",
        (),
        {
            "process_rules": {
                "runtime_verifier_require_deployment_files": True,
                "deployment_planner_required_files": {
                    "agent_output/deployment/custom.Dockerfile": "FROM scratch\n",
                    "agent_output/deployment/custom-compose.yml": "services: {}\n",
                },
            }
        },
    )
    result = await RuntimeVerifier(tmp_path, organization=org).verify()
    assert result.ok is False
    assert any("custom.Dockerfile" in err for err in result.errors)


@pytest.mark.asyncio
async def test_runtime_verifier_uses_profile_policy_commands(tmp_path: Path):
    agent_output = tmp_path / "agent_output"
    agent_output.mkdir(parents=True, exist_ok=True)
    (agent_output / "main.py").write_text("print('ok')\n", encoding="utf-8")
    org = type(
        "Org",
        (),
        {
            "process_rules": {
                "runtime_verifier_stack_profile": "python",
                "runtime_verifier_commands_by_profile": {
                    "python": [[sys.executable, "-c", "print('profile')"]],
                },
            }
        },
    )
    result = await RuntimeVerifier(tmp_path, organization=org).verify()
    assert result.ok is True
    assert len(result.command_results) == 1
    assert result.command_results[0]["policy_source"] == "profile_policy:python"


@pytest.mark.asyncio
async def test_runtime_verifier_classifies_timeout_failures(tmp_path: Path):
    agent_output = tmp_path / "agent_output"
    agent_output.mkdir(parents=True, exist_ok=True)
    (agent_output / "main.py").write_text("print('ok')\n", encoding="utf-8")
    org = type(
        "Org",
        (),
        {
            "process_rules": {
                "runtime_verifier_timeout_sec": 1,
                "runtime_verifier_commands": [[sys.executable, "-c", "import time; time.sleep(2)"]],
            }
        },
    )
    result = await RuntimeVerifier(tmp_path, organization=org).verify()
    assert result.ok is False
    assert result.command_results[0]["failure_class"] == "timeout"
    assert result.failure_breakdown.get("timeout", 0) >= 1


@pytest.mark.asyncio
async def test_runtime_verifier_backend_profile_requires_backend_deployment_defaults(tmp_path: Path):
    agent_output = tmp_path / "agent_output"
    agent_output.mkdir(parents=True, exist_ok=True)
    (agent_output / "main.py").write_text("print('ok')\n", encoding="utf-8")
    org = type(
        "Org",
        (),
        {
            "process_rules": {
                "project_surface_profile": "backend_only",
                "runtime_verifier_require_deployment_files": True,
            }
        },
    )
    result = await RuntimeVerifier(
        tmp_path,
        organization=org,
        project_surface_profile="backend_only",
    ).verify()
    assert result.ok is False
    joined = "\n".join(result.errors)
    assert "agent_output/deployment/Dockerfile" in joined
    assert "docker-compose.yml" not in joined


@pytest.mark.asyncio
async def test_runtime_verifier_microservices_pattern_requires_microservices_deployment_defaults(tmp_path: Path):
    agent_output = tmp_path / "agent_output"
    agent_output.mkdir(parents=True, exist_ok=True)
    (agent_output / "main.py").write_text("print('ok')\n", encoding="utf-8")
    org = type(
        "Org",
        (),
        {
            "process_rules": {
                "runtime_verifier_require_deployment_files": True,
            }
        },
    )
    result = await RuntimeVerifier(
        tmp_path,
        organization=org,
        architecture_pattern="microservices",
    ).verify()
    assert result.ok is False
    joined = "\n".join(result.errors)
    assert "Dockerfile.api" in joined
    assert "Dockerfile.worker" in joined


@pytest.mark.asyncio
async def test_runtime_verifier_rejects_shell_string_commands(tmp_path: Path):
    """Layer: contract. Verifies runtime verifier refuses shell-string commands instead of executing them with shell=True."""
    agent_output = tmp_path / "agent_output"
    agent_output.mkdir(parents=True, exist_ok=True)
    (agent_output / "main.py").write_text("print('ok')\n", encoding="utf-8")
    org = type(
        "Org",
        (),
        {
            "process_rules": {
                "runtime_verifier_commands": ["python -c \"print('unsafe')\""],
            }
        },
    )

    result = await RuntimeVerifier(tmp_path, organization=org).verify()

    assert result.ok is False
    assert result.command_results[0]["returncode"] == 126
    assert "argv lists" in result.command_results[0]["stderr"]


@pytest.mark.asyncio
async def test_runtime_verifier_reports_when_no_builtin_defaults_exist_for_node_profile(tmp_path: Path):
    """Layer: contract. Verifies command-plan source is explicit when a stack profile has no builtin verifier commands."""
    agent_output = tmp_path / "agent_output"
    agent_output.mkdir(parents=True, exist_ok=True)
    (agent_output / "package.json").write_text("{\"name\": \"demo\"}\n", encoding="utf-8")
    org = type(
        "Org",
        (),
        {
            "process_rules": {
                "runtime_verifier_stack_profile": "node",
            }
        },
    )

    plan = await RuntimeVerifier(tmp_path, organization=org)._resolve_runtime_command_plan()

    assert plan["commands"] == []
    assert plan["source"] == "profile_default_none:node"


@pytest.mark.asyncio
async def test_runtime_verifier_runs_app_entrypoint_when_artifact_contract_is_app(tmp_path: Path):
    agent_output = tmp_path / "agent_output"
    soak_matrix = agent_output / "soak_matrix"
    soak_matrix.mkdir(parents=True, exist_ok=True)
    (soak_matrix / "a.txt").write_text("alpha\n", encoding="utf-8")
    (agent_output / "main.py").write_text(
        "import json\n"
        "from pathlib import Path\n"
        "root = Path(__file__).resolve().parent / 'soak_matrix'\n"
        "files = sorted(str(path.relative_to(root)).replace('\\\\', '/') for path in root.rglob('*') if path.is_file())\n"
        "print(json.dumps({'files_count': len(files), 'files_list': files}))\n",
        encoding="utf-8",
    )

    result = await RuntimeVerifier(
        tmp_path,
        artifact_contract={"kind": "app", "entrypoint_path": "agent_output/main.py"},
        issue_params={
            "runtime_verifier": {
                "expect_json_stdout": True,
                "json_assertions": [
                    {"path": "files_count", "op": "gte", "value": 1},
                    {"path": "files_list", "op": "len_gte", "value": 1},
                ],
            }
        },
    ).verify()

    assert result.ok is True
    assert len(result.command_results) == 2
    assert result.command_results[-1]["command_display"].endswith("agent_output/main.py")
    assert result.command_results[-1]["stdout_contract_ok"] is True
    assert result.command_results[-1]["stdout_json"]["files_count"] == 1


@pytest.mark.asyncio
async def test_runtime_verifier_does_not_run_entrypoint_when_artifact_contract_is_artifact(tmp_path: Path):
    agent_output = tmp_path / "agent_output"
    agent_output.mkdir(parents=True, exist_ok=True)
    (agent_output / "requirements.txt").write_text("repo-local soak requirements\n", encoding="utf-8")
    (agent_output / "main.py").write_text("raise SystemExit('should not run')\n", encoding="utf-8")

    result = await RuntimeVerifier(
        tmp_path,
        artifact_contract={"kind": "artifact", "primary_output": "agent_output/requirements.txt"},
    ).verify()

    assert result.ok is True
    assert len(result.command_results) == 1
    assert result.command_results[0]["command_display"].endswith("-m compileall -q agent_output")


@pytest.mark.asyncio
async def test_runtime_verifier_fails_when_stdout_json_assertions_fail(tmp_path: Path):
    agent_output = tmp_path / "agent_output"
    agent_output.mkdir(parents=True, exist_ok=True)
    (agent_output / "main.py").write_text("import json\nprint(json.dumps({'files_count': 0, 'files_list': []}))\n", encoding="utf-8")

    result = await RuntimeVerifier(
        tmp_path,
        artifact_contract={"kind": "app", "entrypoint_path": "agent_output/main.py"},
        issue_params={
            "runtime_verifier": {
                "expect_json_stdout": True,
                "json_assertions": [
                    {"path": "files_count", "op": "gte", "value": 1},
                ],
            }
        },
    ).verify()

    assert result.ok is False
    assert result.failure_breakdown.get("command_failed", 0) >= 1
    assert "runtime stdout assertion failed" in "\n".join(result.errors)
