"""The gardener harness example runs a real governed agent submission end to end.

Each test drives ``examples/gardener_harness/gardener_harness.py`` the way
gardener's ``command`` harness does (prompt on stdin, ``GARDENER_HARNESS_*``
environment) against a throwaway git repository. The wrapper runs the real
``orket agent submit`` CLI with the deterministic fixture provider, so the
extension subprocess, control-plane store and advisory-report verifier are all
real; only model output is fixture data, which is never live-model proof.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = REPO_ROOT / "examples" / "gardener_harness"
WRAPPER = EXAMPLE / "gardener_harness.py"


def _orket_bin() -> str:
    found = shutil.which("orket", path=str(Path(sys.executable).parent)) or shutil.which("orket")
    if found is None:
        pytest.fail("the orket console script must be installed with the package for this example")
    return found


def _target_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "target"
    repo.mkdir()
    (repo / "README.md").write_text("# target\nBuild with make.\n", encoding="utf-8")
    (repo / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
    for argv in (["git", "init", "-q"], ["git", "add", "-A"],
                 ["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-q", "-m", "init"]):
        subprocess.run(argv, cwd=repo, check=True, capture_output=True)
    return repo


def _run(tmp_path: Path, repo: Path, *, mode: str = "report", prompt: str | None = None,
         extra_env: dict[str, str] | None = None) -> tuple[int, dict]:
    conventions = tmp_path / "conventions"
    conventions.mkdir(exist_ok=True)
    (conventions / "CHECKLIST.md").write_text("1. README exists.\n", encoding="utf-8")
    spec = {"mode": mode, "tools": ["Read", "Grep", "Glob"], "permission_mode": "plan",
            "allowed_tools": [], "add_dirs": [str(conventions)], "merge_allowed": False}
    env = {**os.environ, "GARDENER_HARNESS_MODE": mode, "GARDENER_HARNESS_SPEC": json.dumps(spec),
           "GARDENER_HARNESS_TIMEOUT": "300", "ORKET_GARDENER_PROVIDER": "fixture",
           "ORKET_GARDENER_ORKET_BIN": _orket_bin(), "ORKET_GARDENER_WORK_DIR": str(tmp_path / "work"),
           **(extra_env or {})}
    env.pop("GARDENER_HARNESS_MODEL", None)
    text = prompt if prompt is not None else f"Audit this repository against {conventions / 'CHECKLIST.md'}."
    proc = subprocess.run([sys.executable, str(WRAPPER)], input=text, cwd=repo, env=env,
                          capture_output=True, text=True, timeout=600)
    return proc.returncode, json.loads(proc.stdout)


# Layer: integration
def test_report_dispatch_completes_through_the_advisory_report_verifier(tmp_path):
    repo = _target_repo(tmp_path)
    before = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout

    code, envelope = _run(tmp_path, repo)

    assert code == 0, envelope
    assert envelope["is_error"] is False and envelope["blocked"] is False
    assert envelope["result"].startswith("Deterministic fixture report over")
    assert "verified by the advisory-report verifier" in envelope["result"]
    assert "CHECKLIST.md" in envelope["result"] and "README.md" in envelope["result"]
    assert envelope["session_id"].startswith("orket:gardener-")
    submit = json.loads(next((tmp_path / "work").glob("*/submit.json")).read_text(encoding="utf-8"))
    assert submit["proof_posture"] == "deterministic_fixture_not_live_model"
    assert submit["final_truth"]["completion_classification"] == "completion_satisfied"
    assert submit["authoritative_result"]["ref"] == submit["final_truth"]["authoritative_result_ref"]
    assert json.loads(submit["authoritative_result"]["advisory_proposal"])["source_refs"]
    after = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout
    assert before == after == ""


# Layer: integration
@pytest.mark.parametrize("mode", ["implement", "file-issue", "tend", "create-dev-loop"])
def test_every_mode_but_report_is_refused_before_orket_runs(tmp_path, mode):
    code, envelope = _run(tmp_path, _target_repo(tmp_path), mode=mode)
    assert code == 2
    assert envelope["is_error"] is True and "report mode only" in envelope["result"]
    assert not (tmp_path / "work").exists()


# Layer: integration
def test_a_live_provider_without_a_model_is_a_configuration_error(tmp_path):
    code, envelope = _run(tmp_path, _target_repo(tmp_path), extra_env={"ORKET_GARDENER_PROVIDER": "ollama"})
    assert code == 2
    assert envelope["is_error"] is True and "GARDENER_HARNESS_MODEL" in envelope["result"]


# Layer: integration
def test_example_extension_passes_strict_host_validation():
    proc = subprocess.run([_orket_bin(), "ext", "validate", str(EXAMPLE / "extension"), "--strict", "--json"],
                          capture_output=True, text=True, timeout=300)
    payload = json.loads(proc.stdout)
    assert proc.returncode == 0 and payload["ok"] is True, payload
