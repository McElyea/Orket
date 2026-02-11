from orket.domain.verification import VerificationEngine
from orket.schema import IssueVerification, VerificationScenario
import subprocess


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
