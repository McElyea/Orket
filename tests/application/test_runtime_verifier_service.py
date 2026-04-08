from __future__ import annotations

import sys
from pathlib import Path

import pytest

from orket.application.services.runtime_verifier import RuntimeVerifier, build_runtime_guard_contract


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
    assert result.command_results[0]["evidence_class"] == "syntax_only"
    assert result.failure_breakdown == {}
    assert result.overall_evidence_class == "syntax_only"
    assert result.evidence_summary["syntax_only"]["evaluated"] is True
    assert result.evidence_summary["command_execution"]["evaluated"] is False
    assert result.evidence_summary["behavioral_verification"]["evaluated"] is False
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
    assert result.guard_contract.violations[0].rule_id == "RUNTIME_VERIFIER.FAIL.0"
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
    assert result.command_results[0]["evidence_class"] == "command_execution"
    assert result.overall_evidence_class == "command_execution"


@pytest.mark.asyncio
async def test_runtime_verifier_runs_issue_scoped_behavioral_commands(tmp_path: Path):
    agent_output = tmp_path / "agent_output"
    runtime_root = agent_output / "challenge_runtime"
    tests_root = agent_output / "tests"
    runtime_root.mkdir(parents=True, exist_ok=True)
    tests_root.mkdir(parents=True, exist_ok=True)
    (agent_output / "main.py").write_text(
        "import json\n"
        "print(json.dumps({'validated_count': 2, 'layer_count': 3, 'dependency_cycle': True, 'cycle_policy': 'validation_rejects_cycle', 'cycle_fixture_result': 'expected_rejection', 'checkpoint_written': True, 'resumed_terminal_state': 'completed'}))\n",
        encoding="utf-8",
    )
    (runtime_root / "reporting.py").write_text(
        "import json\n"
        "def format_report(data):\n"
        "    return json.dumps(data)\n",
        encoding="utf-8",
    )
    (tests_root / "test_smoke.py").write_text("def test_smoke():\n    assert True\n", encoding="utf-8")

    result = await RuntimeVerifier(
        tmp_path,
        artifact_contract={"kind": "artifact", "primary_output": "agent_output/README.md"},
        issue_params={
            "runtime_verifier": {
                "commands": [
                    {"argv": ["python", "-m", "pytest", "-q", "tests"], "cwd": "agent_output"},
                    {
                        "argv": [
                            "python",
                            "-c",
                            "import json; from challenge_runtime.reporting import format_report; rendered = format_report({'ok': True}); payload = json.loads(rendered); print(json.dumps(payload))",
                        ],
                        "cwd": "agent_output",
                    },
                    {"argv": ["python", "agent_output/main.py"], "cwd": "."},
                ],
                "expect_json_stdout": True,
                "json_assertions": [
                    {"path": "validated_count", "op": "gte", "value": 2},
                    {"path": "layer_count", "op": "gte", "value": 3},
                    {"path": "dependency_cycle", "op": "eq", "value": True},
                    {"path": "cycle_policy", "op": "eq", "value": "validation_rejects_cycle"},
                    {"path": "cycle_fixture_result", "op": "eq", "value": "expected_rejection"},
                    {"path": "checkpoint_written", "op": "eq", "value": True},
                    {"path": "resumed_terminal_state", "op": "eq", "value": "completed"},
                ],
            }
        },
    ).verify()

    assert result.ok is True
    assert len(result.command_results) == 3
    assert result.command_results[0]["policy_source"] == "issue_override"
    assert result.command_results[0]["command_text"] == "python -m pytest -q tests"
    assert result.command_results[0]["working_directory"] == "agent_output"
    assert result.command_results[0]["exit_code"] == 0
    assert result.command_results[0]["outcome"] == "pass"
    assert result.command_results[1]["command_text"].startswith("python -c import json;")
    assert result.command_results[1]["working_directory"] == "agent_output"
    assert result.command_results[1]["exit_code"] == 0
    assert result.command_results[2]["command_text"] == "python agent_output/main.py"
    assert result.command_results[2]["working_directory"] == "."
    assert result.command_results[2]["evidence_class"] == "behavioral_verification"
    assert result.command_results[2]["stdout_contract_ok"] is True
    assert result.command_results[2]["stdout_json"]["validated_count"] == 2
    assert result.command_results[2]["stdout_json"]["cycle_policy"] == "validation_rejects_cycle"
    assert result.overall_evidence_class == "behavioral_verification"
    assert result.evidence_summary["behavioral_verification"]["evaluated"] is True


@pytest.mark.asyncio
async def test_runtime_verifier_supports_nested_list_json_assertions(tmp_path: Path):
    agent_output = tmp_path / "agent_output"
    agent_output.mkdir(parents=True, exist_ok=True)
    (agent_output / "main.py").write_text(
        "import json\n"
        "print(json.dumps({'layers': [['task1'], ['task2', 'task3'], ['task4']]}))\n",
        encoding="utf-8",
    )

    result = await RuntimeVerifier(
        tmp_path,
        issue_params={
            "runtime_verifier": {
                "commands": [
                    {"argv": ["python", "agent_output/main.py"], "cwd": "."},
                ],
                "expect_json_stdout": True,
                "json_assertions": [
                    {"path": "layers[1][1]", "op": "eq", "value": "task3"},
                ],
            }
        },
    ).verify()

    assert result.ok is True
    assert result.command_results[0]["stdout_contract_ok"] is True
    assert result.command_results[0]["stdout_json"]["layers"][1][1] == "task3"


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
async def test_runtime_verifier_preserves_traceback_tail_for_long_inline_commands(tmp_path: Path):
    """Layer: contract. Verifies long inline verifier commands still surface the exception tail in stored stderr and summary errors."""
    agent_output = tmp_path / "agent_output"
    agent_output.mkdir(parents=True, exist_ok=True)
    (agent_output / "main.py").write_text("print('ok')\n", encoding="utf-8")
    padding = "x=0;" * 700

    result = await RuntimeVerifier(
        tmp_path,
        issue_params={
            "runtime_verifier": {
                "commands": [
                    {"argv": ["python", "-c", padding + "raise RuntimeError('tail-visible')"], "cwd": "agent_output"},
                ]
            }
        },
    ).verify()

    assert result.ok is False
    assert result.command_results[0]["returncode"] == 1
    assert "RuntimeError: tail-visible" in result.command_results[0]["stderr"]
    assert result.errors
    assert result.errors[0].startswith("runtime command failed [command_failed] cwd=agent_output:")
    assert "RuntimeError: tail-visible" in result.errors[0]


@pytest.mark.asyncio
async def test_runtime_verifier_rejects_issue_command_cwd_escape(tmp_path: Path):
    agent_output = tmp_path / "agent_output"
    agent_output.mkdir(parents=True, exist_ok=True)

    result = await RuntimeVerifier(
        tmp_path,
        issue_params={
            "runtime_verifier": {
                "commands": [
                    {"argv": ["python", "-V"], "cwd": ".."},
                ]
            }
        },
    ).verify()

    assert result.ok is False
    assert result.command_results[0]["returncode"] == 126
    assert result.command_results[0]["working_directory"] == ".."
    assert result.command_results[0]["outcome"] == "fail"
    assert "escapes workspace" in result.command_results[0]["stderr"]


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
    assert result.command_results[-1]["evidence_class"] == "behavioral_verification"
    assert result.command_results[-1]["stdout_contract_ok"] is True
    assert result.command_results[-1]["stdout_json"]["files_count"] == 1
    assert result.overall_evidence_class == "behavioral_verification"


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
    assert result.command_results[0]["evidence_class"] == "syntax_only"
    assert result.overall_evidence_class == "syntax_only"


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
    assert result.command_results[-1]["failure_class"] == "stdout_assertion_failed"
    assert result.command_results[-1]["outcome"] == "fail"
    assert result.failure_breakdown.get("stdout_assertion_failed", 0) >= 1
    assert "runtime stdout assertion failed" in "\n".join(result.errors)


@pytest.mark.asyncio
async def test_runtime_verifier_classifies_stdout_json_parse_failures(tmp_path: Path):
    agent_output = tmp_path / "agent_output"
    agent_output.mkdir(parents=True, exist_ok=True)
    (agent_output / "main.py").write_text("print('not-json')\n", encoding="utf-8")

    result = await RuntimeVerifier(
        tmp_path,
        artifact_contract={"kind": "app", "entrypoint_path": "agent_output/main.py"},
        issue_params={
            "runtime_verifier": {
                "expect_json_stdout": True,
            }
        },
    ).verify()

    assert result.ok is False
    assert result.command_results[-1]["failure_class"] == "stdout_json_parse_failed"
    assert result.command_results[-1]["outcome"] == "fail"
    assert result.command_results[-1]["stdout_contract_ok"] is False
    assert result.command_results[-1]["stdout_contract_error"] == "json_parse_failed"
    assert result.failure_breakdown.get("stdout_json_parse_failed", 0) >= 1


def test_runtime_verifier_resolve_command_cwd_rejects_escape_with_relative_workspace_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Layer: unit. Verifies relative workspace roots are resolved before containment checks."""
    monkeypatch.chdir(tmp_path)

    assert RuntimeVerifier._resolve_command_cwd("../../../etc", Path()) is None


def test_runtime_verifier_classifies_oom_returncode() -> None:
    """Layer: unit. Verifies Linux OOM/SIGKILL exit status is explicit in failure breakdowns."""
    assert RuntimeVerifier._failure_class_from_returncode(137) == "oom_killed"


@pytest.mark.asyncio
async def test_runtime_verifier_unknown_json_assertion_op_is_explicit_failure(tmp_path: Path):
    """Layer: contract. Verifies unsupported stdout assertion ops fail loudly instead of silently returning false."""
    agent_output = tmp_path / "agent_output"
    agent_output.mkdir(parents=True, exist_ok=True)
    (agent_output / "main.py").write_text("import json\nprint(json.dumps({'files_count': 1}))\n", encoding="utf-8")

    result = await RuntimeVerifier(
        tmp_path,
        artifact_contract={"kind": "app", "entrypoint_path": "agent_output/main.py"},
        issue_params={
            "runtime_verifier": {
                "expect_json_stdout": True,
                "json_assertions": [
                    {"path": "files_count", "op": "approximately", "value": 1},
                ],
            }
        },
    ).verify()

    assert result.ok is False
    assert result.command_results[-1]["failure_class"] == "stdout_assertion_failed"
    assert "unknown assertion op" in "\n".join(result.errors)


def test_build_runtime_guard_contract_surfaces_multiple_errors_and_truncation() -> None:
    """Layer: unit. Verifies guard contracts preserve one violation per runtime verifier error."""
    contract = build_runtime_guard_contract(ok=False, errors=["first failure", "x" * 300])

    assert len(contract.violations) == 2
    assert [violation.rule_id for violation in contract.violations] == [
        "RUNTIME_VERIFIER.FAIL.0",
        "RUNTIME_VERIFIER.FAIL.1",
    ]
    assert contract.violations[0].message == "first failure"
    assert contract.violations[1].evidence == "x" * 240
    assert contract.violations[1].evidence_truncated is True


@pytest.mark.asyncio
async def test_runtime_verifier_reports_not_evaluated_when_no_targets_or_commands(tmp_path: Path) -> None:
    """Layer: contract. Verifies empty verifier runs report not-evaluated evidence instead of implying proof."""
    result = await RuntimeVerifier(tmp_path).verify()

    assert result.ok is True
    assert result.checked_files == []
    assert result.command_results == []
    assert result.overall_evidence_class == "not_evaluated"
    assert result.evidence_summary["syntax_only"]["evaluated"] is False
    assert result.evidence_summary["command_execution"]["evaluated"] is False
    assert result.evidence_summary["behavioral_verification"]["evaluated"] is False
    assert {item["check"] for item in result.evidence_summary["not_evaluated"]} == {
        "syntax_only",
        "command_execution",
        "behavioral_verification",
    }
