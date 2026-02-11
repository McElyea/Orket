from orket.domain.verification import VerificationEngine
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
