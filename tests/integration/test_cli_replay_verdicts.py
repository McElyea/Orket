"""Integration: real CLI processes separate wrong answers from differing replays."""
from pathlib import Path

import pytest

from scripts.benchmarks.live_card_benchmark_runner import _evaluate_quality

pytestmark = pytest.mark.integration


def _checks(tmp_path: Path, source: str, expected: str):
    program = tmp_path / "agent_output/main.py"
    program.parent.mkdir()
    program.write_text(source, encoding="utf-8")
    task = {"acceptance_contract": {"mode": "system"}, "evaluation": {
        "type": "cli_examples", "entrypoint": "agent_output/main.py", "examples": [
            {"args": [], "expected_stdout": expected, "expected_stderr": "", "expected_exit_code": 0}]}}
    result = _evaluate_quality(task, source, tmp_path)
    return result, {check["name"]: check for check in result["checks"]}


def test_repeatable_wrong_answer_is_failed_correctness_and_observed_repeatability(tmp_path):
    result, checks = _checks(tmp_path, "print('wrong')\n", "right\n")
    assert not result["passed"]
    assert not checks["cli_example_cases_pass"]["passed"]
    assert checks["cli_examples_deterministic_replay"]["passed"]
    assert checks["cli_examples_deterministic_replay"]["complete"]


def test_matching_first_answer_does_not_conceal_different_second_execution(tmp_path):
    source = ("from pathlib import Path\np = Path('counter.txt')\n"
              "value = int(p.read_text()) + 1 if p.exists() else 1\np.write_text(str(value))\nprint(value)\n")
    result, checks = _checks(tmp_path, source, "1\n")
    assert not result["passed"]
    assert not checks["cli_example_cases_pass"]["passed"]
    assert not checks["cli_examples_deterministic_replay"]["passed"]
    assert "different CLI outputs" in checks["cli_examples_deterministic_replay"]["detail"]
