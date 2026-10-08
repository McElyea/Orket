"""Native filesystem/probe controls for the installed-candidate acceptance producer."""
from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from scripts.ci.candidate_install_support import inspect_wheel, observe_quickstart, snapshot_packages

pytestmark = pytest.mark.integration


def test_snapshot_uses_git_visible_dirty_inputs_and_excludes_cached_builds(tmp_path):
    repo, target = tmp_path / "repo", tmp_path / "snapshot"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    authored = {"pyproject.toml": "current", "README.md": "readme", "LICENSE": "license",
                "orket/__init__.py": "", "orket_extension_sdk/__init__.py": "",
                "orket_extension_sdk/pyproject.toml": "sdk", "orket/data.json": '{"real":true}'}
    for name, content in authored.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (repo / ".gitignore").write_text("ignored.json\n", encoding="utf-8")
    for name in ("orket/ignored.json", "orket/build/poison.py", "orket/stale.egg-info/PKG-INFO"):
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("must not enter candidate", encoding="utf-8")
    first = snapshot_packages(repo, target)
    assert set(first["inputs"]) == set(authored)
    assert (target / "pyproject.toml").read_text() == "current"
    (repo / "pyproject.toml").write_text("changed uncommitted input", encoding="utf-8")
    second = snapshot_packages(repo, tmp_path / "second")
    assert first["sha256"] != second["sha256"]
    assert not (target / "orket/build").exists()


@pytest.mark.parametrize("defect", ["missing-resource", "wrong-bytes", "namespace-overlap"])
def test_wheel_observer_rejects_missing_stale_and_overlapping_contents(tmp_path, defect):
    source = tmp_path / "source"
    (source / "orket").mkdir(parents=True)
    (source / "orket/__init__.py").write_bytes(b"")
    (source / "orket/required.json").write_bytes(b"{}")
    wheel = tmp_path / "candidate.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("orket/__init__.py", b"")
        if defect != "missing-resource":
            archive.writestr("orket/required.json", b"stale" if defect == "wrong-bytes" else b"{}")
        if defect == "namespace-overlap":
            archive.writestr("orket_extension_sdk/__init__.py", b"")
    with pytest.raises(ValueError):
        inspect_wheel(wheel, source, "orket")


def test_success_ledger_cannot_replace_expected_file_effect(tmp_path):
    ledger = tmp_path / ".orket/quickstart/runs/test/ledger.jsonl"
    ledger.parent.mkdir(parents=True)
    ledger.write_text(json.dumps({"event_type": "run_finished", "payload": {"terminal_status": "approved_executed"}}),
                      encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        observe_quickstart(tmp_path, "approve")
    output = tmp_path / "quickstart_out/hello_from_orket.txt"
    output.parent.mkdir()
    output.write_bytes(b"forbidden effect")
    with pytest.raises(ValueError, match="Denied quickstart"):
        observe_quickstart(tmp_path, "deny")


def test_native_probe_refuses_an_interpreter_outside_candidate_prefix(tmp_path):
    probe = Path(__file__).resolve().parents[2] / "scripts/ci/installed_candidate_probe.py"
    result = subprocess.run([sys.executable, "-I", str(probe), str(tmp_path / "checkout"),
                             str(tmp_path / "candidate"), "unused-core.whl", "unused-sdk.whl"],
                            cwd=tmp_path, capture_output=True, timeout=30)
    assert result.returncode != 0
    assert b"not in the isolated external environment" in result.stderr


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
def test_quickstart_text_contract_retains_actual_native_byte_hash(tmp_path, newline):
    import hashlib

    ledger = tmp_path / ".orket/quickstart/runs/test/ledger.jsonl"
    ledger.parent.mkdir(parents=True)
    ledger.write_text(json.dumps({"event_type": "run_finished", "payload": {"terminal_status": "approved_executed"}}),
                      encoding="utf-8")
    output = tmp_path / "quickstart_out/hello_from_orket.txt"
    output.parent.mkdir()
    content = b"hello from a governed Orket action" + newline
    output.write_bytes(content)
    observed = observe_quickstart(tmp_path, "approve")
    assert observed["output"]["sha256"] == hashlib.sha256(content).hexdigest()
