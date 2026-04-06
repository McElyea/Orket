import json
import subprocess

import pytest

from orket.core.domain.verification import VerificationEngine, VerificationSecurityError
from orket.schema import IssueVerification, VerificationScenario


def test_verification_runs_in_subprocess_and_passes(tmp_path):
    workspace = tmp_path / "workspace"
    verification_dir = workspace / "verification"
    verification_dir.mkdir(parents=True)
    fixture_path = verification_dir / "fixture_pass.py"
    fixture_path.write_text(
        "def verify(input_data):\n"
        "    return input_data.get('value', 0)\n",
        encoding="utf-8",
    )

    verification = IssueVerification(
        fixture_path="verification/fixture_pass.py",
        scenarios=[
            VerificationScenario(
                id="S1",
                description="simple pass",
                input_data={"value": 7},
                expected_output=7,
            )
        ],
    )

    result = VerificationEngine.verify(verification, workspace)
    assert result.passed == 1
    assert result.failed == 0


def test_verification_subprocess_timeout_marks_failure(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    verification_dir = workspace / "verification"
    verification_dir.mkdir(parents=True)
    fixture_path = verification_dir / "fixture_timeout.py"
    fixture_path.write_text(
        "def verify(input_data):\n"
        "    while True:\n"
        "        pass\n",
        encoding="utf-8",
    )

    verification = IssueVerification(
        fixture_path="verification/fixture_timeout.py",
        scenarios=[
            VerificationScenario(
                id="T1",
                description="timeout",
                input_data={"value": 1},
                expected_output=1,
            )
        ],
    )

    monkeypatch.setenv("ORKET_VERIFY_TIMEOUT_SEC", "1")
    result = VerificationEngine.verify(verification, workspace)
    assert result.failed == 1
    assert any("timeout" in entry.lower() for entry in result.logs)


def test_verification_missing_fixture_marks_all_failed(tmp_path):
    workspace = tmp_path / "workspace"
    (workspace / "verification").mkdir(parents=True)

    verification = IssueVerification(
        fixture_path="verification/missing_fixture.py",
        scenarios=[
            VerificationScenario(
                id="M1",
                description="missing fixture",
                input_data={"value": 1},
                expected_output=1,
            )
        ],
    )

    result = VerificationEngine.verify(verification, workspace)
    assert result.failed == 1
    assert result.passed == 0
    assert any("not found" in entry.lower() for entry in result.logs)


def test_verification_subprocess_fatal_exit_marks_all_failed(tmp_path):
    workspace = tmp_path / "workspace"
    verification_dir = workspace / "verification"
    verification_dir.mkdir(parents=True)
    fixture_path = verification_dir / "fixture_fatal_exit.py"
    fixture_path.write_text(
        "raise SystemExit(3)\n",
        encoding="utf-8",
    )

    verification = IssueVerification(
        fixture_path="verification/fixture_fatal_exit.py",
        scenarios=[
            VerificationScenario(
                id="F1",
                description="fatal subprocess exit",
                input_data={"value": 1},
                expected_output=1,
            )
        ],
    )

    result = VerificationEngine.verify(verification, workspace)
    assert result.failed == 1
    assert result.passed == 0
    assert any("subprocess exit code" in entry.lower() for entry in result.logs)


def test_verification_parsed_not_ok_marks_all_failed(tmp_path):
    workspace = tmp_path / "workspace"
    verification_dir = workspace / "verification"
    verification_dir.mkdir(parents=True)
    fixture_path = verification_dir / "fixture_bad_syntax.py"
    fixture_path.write_text(
        "def verify(input_data)\n"
        "    return 1\n",
        encoding="utf-8",
    )

    verification = IssueVerification(
        fixture_path="verification/fixture_bad_syntax.py",
        scenarios=[
            VerificationScenario(
                id="B1",
                description="bad syntax fixture",
                input_data={"value": 1},
                expected_output=1,
            )
        ],
    )

    result = VerificationEngine.verify(verification, workspace)
    assert result.failed == 1
    assert result.passed == 0
    assert any("fatal error" in entry.lower() for entry in result.logs)


def test_verification_subprocess_oserror_marks_all_failed(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    verification_dir = workspace / "verification"
    verification_dir.mkdir(parents=True)
    fixture_path = verification_dir / "fixture_pass.py"
    fixture_path.write_text(
        "def verify(input_data):\n"
        "    return input_data.get('value', 0)\n",
        encoding="utf-8",
    )

    verification = IssueVerification(
        fixture_path="verification/fixture_pass.py",
        scenarios=[
            VerificationScenario(
                id="O1",
                description="oserror path",
                input_data={"value": 1},
                expected_output=1,
            )
        ],
    )

    def raise_oserror(*_args, **_kwargs):
        raise OSError("simulated subprocess failure")

    monkeypatch.setattr(subprocess, "run", raise_oserror)

    result = VerificationEngine.verify(verification, workspace)
    assert result.failed == 1
    assert result.passed == 0
    assert any("fatal error" in entry.lower() for entry in result.logs)


def test_verification_security_allows_fixture_under_verification_root(tmp_path):
    workspace = tmp_path / "workspace"
    verification_dir = workspace / "verification"
    verification_dir.mkdir(parents=True)
    (verification_dir / "fixture_safe.py").write_text(
        "def verify(input_data):\n"
        "    return input_data.get('value', 0)\n",
        encoding="utf-8",
    )

    verification = IssueVerification(
        fixture_path="verification/fixture_safe.py",
        scenarios=[
            VerificationScenario(
                id="S_SAFE",
                description="safe fixture path",
                input_data={"value": 2},
                expected_output=2,
            )
        ],
    )

    result = VerificationEngine.verify(verification, workspace)
    assert result.passed == 1
    assert result.failed == 0


def test_verification_security_rejects_path_traversal_fixture(tmp_path):
    workspace = tmp_path / "workspace"
    (workspace / "verification").mkdir(parents=True)
    (workspace / "agent_output").mkdir(parents=True)
    (workspace / "agent_output" / "fixture.py").write_text(
        "def verify(input_data):\n"
        "    return 1\n",
        encoding="utf-8",
    )

    verification = IssueVerification(
        fixture_path="../agent_output/fixture.py",
        scenarios=[
            VerificationScenario(
                id="S_TRAVERSAL",
                description="malicious fixture path traversal",
                input_data={},
                expected_output=1,
            )
        ],
    )

    with pytest.raises(VerificationSecurityError, match="SECURITY VIOLATION"):
        VerificationEngine.verify(verification, workspace)


def test_verification_production_profile_blocks_unsafe_subprocess(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    verification_dir = workspace / "verification"
    verification_dir.mkdir(parents=True)
    fixture_path = verification_dir / "fixture_pass.py"
    fixture_path.write_text(
        "def verify(input_data):\n"
        "    return input_data.get('value', 0)\n",
        encoding="utf-8",
    )

    verification = IssueVerification(
        fixture_path="verification/fixture_pass.py",
        scenarios=[
            VerificationScenario(
                id="P1",
                description="production guard",
                input_data={"value": 5},
                expected_output=5,
            )
        ],
    )

    monkeypatch.setenv("ORKET_RUNTIME_PROFILE", "production")
    monkeypatch.setenv("ORKET_VERIFY_EXECUTION_MODE", "subprocess")
    monkeypatch.delenv("ORKET_VERIFY_ALLOW_UNSAFE_SUBPROCESS", raising=False)

    result = VerificationEngine.verify(verification, workspace)
    assert result.failed == 1
    assert any("disabled in production profile" in entry.lower() for entry in result.logs)


def test_verification_container_mode_uses_docker_runner(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    verification_dir = workspace / "verification"
    verification_dir.mkdir(parents=True)
    fixture_path = verification_dir / "fixture_pass.py"
    fixture_path.write_text(
        "def verify(input_data):\n"
        "    return input_data.get('value', 0)\n",
        encoding="utf-8",
    )

    verification = IssueVerification(
        fixture_path="verification/fixture_pass.py",
        scenarios=[
            VerificationScenario(
                id="C1",
                description="container mode",
                input_data={"value": 9},
                expected_output=9,
            )
        ],
    )

    monkeypatch.setenv("ORKET_VERIFY_EXECUTION_MODE", "container")

    captured = {"cmd": None}

    def fake_run(command, **kwargs):
        captured["cmd"] = list(command)
        payload = json.loads(kwargs.get("input") or "{}")
        scenario = (payload.get("scenarios") or [{}])[0]
        stdout_payload = {
            "ok": True,
            "results": [
                {
                    "id": scenario.get("id"),
                    "expected_output": scenario.get("expected_output"),
                    "actual_output": scenario.get("expected_output"),
                    "status": "pass",
                    "error": None,
                }
            ],
        }
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=json.dumps(stdout_payload),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = VerificationEngine.verify(verification, workspace)
    assert result.passed == 1
    assert result.failed == 0
    assert captured["cmd"][0] == "docker"
