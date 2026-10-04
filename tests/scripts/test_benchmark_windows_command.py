"""Native Windows proof for benchmark runner command-line argument preservation."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.benchmarks.determinism_cli import split_runner_command
from scripts.benchmarks.live_card_benchmark_runner import _evaluate_quality

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.name != "nt", reason="Native Windows argv proof")]


def test_runner_command_preserves_quoted_paths_and_literal_arguments(tmp_path):
    script = tmp_path / "runner with spaces.py"
    script.write_text("import json, sys\nprint(json.dumps(sys.argv[1:]))\n", encoding="utf-8")
    values = ["two words", 'literal "quotes"', "", "C:\\folder with spaces\\tail\\"]
    command = subprocess.list2cmdline([sys.executable, str(script), *values])
    arguments = split_runner_command(command)
    result = subprocess.run(arguments, capture_output=True, text=True, check=True, timeout=10)
    assert json.loads(result.stdout) == values


def test_explicitly_quoted_interpreter_launches(tmp_path):
    script = tmp_path / "runner.py"
    script.write_text("import sys\nprint(sys.executable)\n", encoding="utf-8")
    command = f'"{sys.executable}" "{script}"'
    result = subprocess.run(split_runner_command(command), capture_output=True, text=True, check=True, timeout=10)
    assert Path(result.stdout.strip()).samefile(sys.executable)


def test_cli_example_verification_retains_selected_interpreter(tmp_path):
    program = tmp_path / "agent_output/main.py"
    program.parent.mkdir()
    source = 'import sys\nif __name__ == "__main__":\n    print(sys.executable)\n'
    program.write_text(source, encoding="utf-8")
    task = {"acceptance_contract": {"mode": "system"}, "evaluation": {
        "type": "cli_examples", "entrypoint": "agent_output/main.py", "examples": [
            {"args": [], "expected_stdout": sys.executable + "\n", "expected_stderr": "", "expected_exit_code": 0}]}}
    result = _evaluate_quality(task, source, tmp_path)
    observed = next(check for check in result["checks"] if check["name"] == "cli_example_cases_pass")
    assert observed["passed"], observed
