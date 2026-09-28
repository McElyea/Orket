"""Native coverage collection must retain branch configuration outside its CWD."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from orket.application.services.command_process_supervisor import CommandProcessSupervisor

ROOT = Path(__file__).resolve().parents[2]


def _prepare(root):
    (root / "foreign").mkdir()
    (root / "temp").mkdir()
    (root / "pyproject.toml").write_text('[tool.coverage.run]\nbranch = true\n', encoding="utf-8")
    (root / "coverage_subject.py").write_text(
        'def choose(flag):\n    if flag:\n        return "yes"\n    return "no"\n', encoding="utf-8")
    # This is a standalone CLI fixture: the real child must supply the second branch.
    (root / "test_subject.py").write_text('''import os
import subprocess
import sys
from coverage_subject import choose

def test_both_processes():
    assert choose(True) == "yes"
    child = subprocess.run([sys.executable, "-c",
        "from coverage_subject import choose; print(choose(False))"],
        cwd=os.environ["COVERAGE_CHILD_CWD"], check=True, capture_output=True, text=True, timeout=30)
    assert child.stdout.strip() == "no"
''', encoding="utf-8")


def _environment(root, foreign):
    # A nested independent measurement must not publish into the outer suite's data.
    excluded = {"PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTHONHOME"}
    values = {key: value for key, value in os.environ.items()
              if key not in excluded and not key.startswith(("COV_CORE_", "COVERAGE_"))}
    return dict(values, PYTHONPATH=str(root), PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1",
                ORKET_DISABLE_SANDBOX="1", TEMP=str(root / "temp"), TMP=str(root / "temp"),
                COVERAGE_FILE=str(root / ".coverage"),
                COVERAGE_CHILD_CWD=str(root / "foreign" if foreign else root))


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("foreign,explicit", [(False, False), (True, False), (True, True)],
                         ids=["same-cwd", "lost-config-counterexample", "explicit-config"])
async def test_branch_coverage_survives_foreign_child_cwd(tmp_path, foreign, explicit):
    await asyncio.to_thread(_prepare, tmp_path)
    report = tmp_path / "coverage.json"
    args = [sys.executable, "-B", "-m", "pytest", "test_subject.py", "-q", "-o", "addopts=",
            "-p", "no:cacheprovider", "--cov=coverage_subject", "--cov-fail-under=89",
            "--cov-report=json:" + str(report), "--basetemp=" + str(tmp_path / "fixtures")]
    if explicit:
        args.append("--cov-config=pyproject.toml")
    owner = CommandProcessSupervisor(tmp_path, cancellation_event="coverage_probe_cancelled")
    result = await owner.run(args, cwd=tmp_path, environment=_environment(tmp_path, foreign), timeout_seconds=90)
    assert result.cleanup_confirmed and result.capture_complete, result.lifetime()
    output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
    if foreign and not explicit:
        # Either mode may be combined first; both orders must refuse mixed data.
        errors = ("Can't combine statement coverage data with branch data",
                  "Can't combine branch coverage data with statement data")
        assert result.returncode == 3 and any(message in output for message in errors), output
        assert not await asyncio.to_thread(report.exists)
    else:
        assert result.returncode == 0, output
        totals = json.loads(await asyncio.to_thread(report.read_text, encoding="utf-8"))["totals"]
        assert totals["percent_covered"] == 100
        assert totals["num_branches"] == totals["covered_branches"] == 2


@pytest.mark.unit
def test_quality_coverage_command_selects_the_authored_configuration():
    """Structural command contract; native behavior is exercised separately above."""
    workflow = (ROOT / ".gitea/workflows/quality.yml").read_text(encoding="utf-8")
    assert "pytest tests/ --cov=orket --cov-config=pyproject.toml --cov-fail-under=89" in workflow
