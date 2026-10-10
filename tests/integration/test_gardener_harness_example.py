"""Integration: native Git/CLI/SDK child/SQLite/HTTP; model output is controlled."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from orket.core.contracts.provider_runtime import DEFAULT_LOCAL_MODEL
from tests.helpers.governed_agent_task import prepare_report_task
from tests.integration.test_local_setup_diagnostics import catalog_server as catalog_server

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "examples/gardener_harness/gardener_harness.py"


def git(root, *arguments, input_text=None):
    result = subprocess.run(["git", "-c", "commit.gpgsign=false", *arguments], cwd=root,
                            input=input_text, capture_output=True, text=True, timeout=30, check=True)
    return result.stdout


def commit(root):
    git(root, "add", "-A")
    git(root, "-c", "user.name=Orket acceptance", "-c", "user.email=proof@example.invalid",
        "commit", "-qm", "Snapshot fixture")


def setup(root):
    catalog, _, _ = prepare_report_task(root)
    target, conventions = root / "target", root / "conventions café with spaces"
    for path in (target, conventions):
        path.mkdir()
        git(path, "init", "-q")
    (target / "README.md").write_text("# Native audit fixture\n", encoding="utf-8")
    (target / "main.py").write_text("print('hello')\n", encoding="utf-8")
    (conventions / "CHECKLIST.md").write_text("Document installation instructions.\n", encoding="utf-8")
    for path in (target, conventions):
        commit(path)
    return catalog, target, conventions


def invoke(root, endpoint, paths, *, mode="report", extra=None):
    catalog, target, conventions = paths
    environment = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1",
        "ORKET_DISABLE_SANDBOX": "1", "GARDENER_HARNESS_MODE": mode,
        "GARDENER_HARNESS_MODEL": DEFAULT_LOCAL_MODEL, "GARDENER_HARNESS_TIMEOUT": "120",
        "GARDENER_HARNESS_SPEC": json.dumps({"mode": mode, "permission_mode": "plan", "merge_allowed": False,
            "tools": ["Read", "Grep", "Glob"], "allowed_tools": [], "add_dirs": [str(conventions)]}),
        "ORKET_GARDENER_CATALOG": str(catalog), "ORKET_GARDENER_WORK_DIR": str(root / "work"),
        "ORKET_GARDENER_PROVIDER_BASE_URL": endpoint}
    environment.pop("ORKET_GARDENER_PROVIDER", None)
    environment.pop("ORKET_DURABLE_ROOT", None)
    environment.update(extra or {})
    process = subprocess.run([sys.executable, str(WRAPPER)], cwd=target, env=environment,
        input=f"Audit main.py against {conventions / 'CHECKLIST.md'}.", capture_output=True,
        text=True, encoding="utf-8", timeout=150)
    assert process.stdout, process.stderr
    return process.returncode, json.loads(process.stdout)


def report_response(request):
    inputs = json.loads(request["messages"][-1]["content"])
    return json.dumps({"sections": {"summary": "Advisory: installation documentation is absent."},
        "source_refs": inputs["required_source_refs"], "limitations": ["Only committed snapshots inspected."],
        "advisory": True})


def test_report_uses_committed_windows_paths_default_provider_and_retained_truth(tmp_path, catalog_server):
    endpoint, state = catalog_server
    state["response"] = report_response
    paths = setup(tmp_path)
    code, envelope = invoke(tmp_path, endpoint, paths)
    assert code == 0, envelope
    assert envelope["is_error"] is False and envelope["blocked"] is False
    assert "Advisory: installation" in envelope["result"]
    assert "verified delivery and source references only" in envelope["result"]
    area = next((tmp_path / "work").glob("run-*"))
    inputs = json.loads((area / "inputs.json").read_bytes())
    context = [item["content"] for item in inputs if item["kind"] == "authoritative_context"]
    assert {item.get("path") for item in context} >= {"README.md", "CHECKLIST.md", "main.py"}
    assert all(item["commit"] for item in context if "text" in item)
    assert state["calls"].count("/v1/chat/completions") == 1
    assert state["request"]["model"] == DEFAULT_LOCAL_MODEL
    run_id = envelope["session_id"].removeprefix("orket:")
    for command in ("inspect", "replay"):
        result = subprocess.run([sys.executable, "-m", "orket.cli", "agent", command, run_id,
            "--db", str(area / "agent.sqlite3"), "--json"], capture_output=True, text=True, timeout=30)
        payload = json.loads(result.stdout)
        assert result.returncode == 0 and payload["ok"], payload
        if command == "replay":
            assert payload["status"] == "matched"
        else:
            assert payload["final_truth"]["completion_classification"] == "completion_satisfied"
            assert payload["iterations"][0]["model_calls"][0]["receipt"]["provider"] == "llama_cpp"
    assert not git(paths[1], "status", "--porcelain") and not git(paths[2], "status", "--porcelain")


@pytest.mark.parametrize("mode", ["implement", "file-issue", "tend", "create-dev-loop"])
def test_write_modes_refuse_without_run_area_or_model(tmp_path, catalog_server, mode):
    endpoint, state = catalog_server
    code, result = invoke(tmp_path, endpoint, setup(tmp_path), mode=mode)
    assert code == 1 and result["is_error"] and "report mode only" in result["result"]
    assert not state["calls"] and not (tmp_path / "work").exists()


@pytest.mark.parametrize("defect", ["symlink", "dirty", "no-git", "oversize"])
def test_incomplete_or_unsafe_snapshots_refuse_before_provider(tmp_path, catalog_server, defect):
    endpoint, state = catalog_server
    paths = setup(tmp_path)
    target = paths[1]
    if defect == "symlink":
        secret = tmp_path / "outside.txt"
        secret.write_text("PRIVATE_REVIEW_SENTINEL", encoding="utf-8")
        (target / "README.md").unlink()
        (target / "README.md").symlink_to(secret)
        commit(target)
        assert git(target, "ls-tree", "HEAD", "README.md").startswith("120000")
    elif defect == "dirty":
        (target / "README.md").write_text("Uncommitted change", encoding="utf-8")
    elif defect == "no-git":
        target = tmp_path / "unversioned"
        target.mkdir()
        (target / "README.md").write_text("No Git metadata", encoding="utf-8")
        paths = paths[0], target, paths[2]
    else:
        (target / "README.md").write_text("x" * 16_385, encoding="utf-8")
        commit(target)
    code, result = invoke(tmp_path, endpoint, paths)
    assert code == 1 and result["is_error"]
    assert "PRIVATE_REVIEW_SENTINEL" not in result["result"]
    assert not state["calls"] and not (tmp_path / "work").exists()


def test_wrong_model_is_blocked_and_never_falls_back(tmp_path, catalog_server):
    endpoint, state = catalog_server
    state["model"] = ""
    code, result = invoke(tmp_path, endpoint, setup(tmp_path))
    assert code == 1 and result["blocked"] and result["is_error"]
    assert "/v1/chat/completions" not in state["calls"]


def test_invalid_model_report_cannot_emit_success(tmp_path, catalog_server):
    endpoint, state = catalog_server
    state["response"] = "{\"report\":\"I fixed everything\"}"
    code, result = invoke(tmp_path, endpoint, setup(tmp_path))
    assert code == 1 and result["is_error"]
    assert "verified delivery" not in result["result"]
    assert state["calls"].count("/v1/chat/completions") == 1


def test_source_change_during_model_call_refuses_final_report(tmp_path, catalog_server):
    endpoint, state = catalog_server
    paths = setup(tmp_path)

    def change_source(request):
        (paths[1] / "README.md").write_text("Changed while model ran", encoding="utf-8")
        return report_response(request)

    state["response"] = change_source
    code, result = invoke(tmp_path, endpoint, paths)
    assert code == 1 and result["is_error"]
    assert "snapshot requires a clean" in result["result"]
    assert state["calls"].count("/v1/chat/completions") == 1
