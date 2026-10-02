"""Integration: actual file selection, Git refusal and refactor rollback evidence."""
import json
import shutil

import pytest

from orket.interfaces.refactor_transaction import run_refactor_transaction
from tests.integration.test_api_generation_refusals import _commit, _no_repository, _prepare, _unborn_repo
from tests.interfaces.test_refactor_transaction_cli import _git, _init_repo

pytestmark = pytest.mark.integration


@pytest.fixture
def repo(tmp_path, monkeypatch):
    return _prepare(tmp_path, monkeypatch, initialize=_init_repo)


def _invoke(**changes):
    return run_refactor_transaction(**{"instruction": "rename User to Member", "scope_inputs": ["src/auth"],
                                       "dry_run": False, "auto_confirm": True, **changes})


def _unchanged(repo, code, **changes):
    before = (repo / "src/auth/user.js").read_bytes()
    result = _invoke(**changes)
    assert result["ok"] is False and result["code"] == code
    assert (repo / "src/auth/user.js").read_bytes() == before
    assert _git(repo, "diff", "--exit-code", "HEAD").returncode == 0
    return result


@pytest.mark.parametrize("changes,code", [
    ({"scope_inputs": []}, "E_SCOPE_REQUIRED"),
    ({"instruction": "rewrite everything"}, "E_UNSUPPORTED_INSTRUCTION"),
    ({"auto_confirm": False}, "E_SCOPE_REQUIRED"),
    ({"scope_inputs": ["absent"]}, "E_TOUCHSET_EMPTY"),
])
def test_refactor_admission_refuses_without_changing_sources(repo, changes, code):
    _unchanged(repo, code, **changes)


@pytest.mark.parametrize("config", ["not-json", "{}", '{"verify":{"profiles":{"default":[]}}}',
    '{"verify":{"profiles":{"default":{"commands":[]}}}}',
    '{"verify":{"profiles":{"default":{"commands":[null]}}}}'])
def test_refactor_requires_parseable_and_runnable_verification_profile(repo, config):
    (repo / "orket.config.json").write_text(config, encoding="utf-8")
    _commit(repo)
    _unchanged(repo, "E_CONFIG_INVALID")


def test_dirty_operator_changes_and_missing_git_refuse_before_selection(repo, tmp_path, monkeypatch):
    sentinel = repo / "operator.txt"
    sentinel.write_text("uncommitted", encoding="utf-8")
    _unchanged(repo, "E_WORKTREE_DIRTY")
    assert sentinel.read_text(encoding="utf-8") == "uncommitted"
    outside = tmp_path / "not-a-repository"
    outside.mkdir()
    _no_repository(outside, monkeypatch)
    result = _invoke()
    assert result["code"] == "E_GIT_REQUIRED" and not result["ok"]
    assert not (outside / "src").exists()


def test_unborn_head_cannot_mutate_discovered_file(tmp_path, monkeypatch):
    root = _unborn_repo(tmp_path, monkeypatch)
    path = root / "src/auth/user.js"
    path.parent.mkdir(parents=True)
    path.write_text("export const User = 1;\n", encoding="utf-8")
    result = _invoke()
    assert result["code"] == "E_INTERNAL" and result["message"] == "Unable to resolve git HEAD."
    assert path.read_text(encoding="utf-8") == "export const User = 1;\n"


def test_binary_and_vendor_files_do_not_expand_directory_touch_set(repo):
    binary = repo / "src/auth/data.bin"
    binary.write_bytes(b"\xff\xfe User")
    blocked = []
    for name in ("node_modules", ".venv", "__pycache__"):
        path = repo / "src/auth" / name / "owned.txt"
        path.parent.mkdir()
        path.write_text("User", encoding="utf-8")
        blocked.append(path)
    _commit(repo)
    result = _invoke()
    assert result["ok"] and result["touch_count"] == 2
    assert binary.read_bytes() == b"\xff\xfe User"
    assert all(path.read_text(encoding="utf-8") == "User" for path in blocked)
    assert "Member" in (repo / "src/auth/user.js").read_text(encoding="utf-8")


def test_explicit_vendor_file_is_refused_by_write_barrier(repo):
    path = repo / "src/auth/node_modules/owned.txt"
    path.parent.mkdir()
    path.write_text("User", encoding="utf-8")
    _commit(repo)
    _unchanged(repo, "E_MODEL_OUTPUT_OUT_OF_SCOPE", scope_inputs=["src/auth/node_modules/owned.txt"])
    assert path.read_text(encoding="utf-8") == "User"


def test_no_change_rename_retains_verified_zero_delta_parity(repo):
    before = (repo / "src/auth/user.js").read_bytes()
    result = _invoke(instruction="rename User to User", scope_inputs=["src/auth/user.js"])
    assert result["ok"] and result["touch_count"] == 1
    assert result["parity"]["changed_file_count"] == 0
    record = json.loads((repo / result["parity"]["artifact_path"]).read_text(encoding="utf-8"))
    row, = record["files"]
    assert row["before_sha256"] == row["after_sha256"] and row["changed"] is False
    assert (repo / "src/auth/user.js").read_bytes() == before


def test_missing_native_verifier_rolls_back_and_records_internal_failure(repo):
    command = "orket-fixture-command-does-not-exist-4ed16c"
    assert shutil.which(command) is None
    (repo / "orket.config.json").write_text(json.dumps({"verify": {"profiles": {
        "default": {"commands": [command]}}}}), encoding="utf-8")
    _commit(repo)
    result = _unchanged(repo, "E_INTERNAL")
    assert "internal I/O error" in result["message"]
    artifacts = list((repo / ".orket/replay_artifacts/refactor").glob("*.json"))
    receipt, = [json.loads(path.read_text(encoding="utf-8")) for path in artifacts]
    assert receipt["result"]["code"] == "E_INTERNAL"


def test_large_native_verifier_failure_retains_bounded_diagnostics_and_revert_parity(repo):
    (repo / "verify.py").write_text(
        "import sys\nprint('BEGIN-EXCLUDED')\nprint(('x' * 300 + '\\n') * 400)\n"
        "print('END-RETAINED')\nsys.exit(9)\n", encoding="utf-8")
    _commit(repo)
    result = _unchanged(repo, "E_VERIFY_FAILED_REVERTED")
    assert result["verify_exit_code"] == 9 and result["parity"]["revert_verified"] is True
    assert result["parity"]["changed_file_count"] == 0
    tail = result["verify_output_tail"]
    assert "END-RETAINED" in tail and "BEGIN-EXCLUDED" not in tail
    assert len(tail.splitlines()) <= 200 and len(tail.encode("utf-8")) <= 32768
