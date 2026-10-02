"""Integration: native Git admission, generation refusal and retained rollback."""
import json
from pathlib import Path

import pytest

from orket.interfaces.api_generation import run_api_add_transaction
from tests.interfaces.test_api_add_transaction_cli import _git, _init_express_fixture

pytestmark = pytest.mark.integration


def _prepare(tmp_path, monkeypatch, initialize=_init_express_fixture):
    repo = initialize(tmp_path).resolve()
    assert repo.is_relative_to(tmp_path.resolve())
    probe = _git(repo, "rev-parse", "--show-toplevel")
    assert probe.returncode == 0 and Path(probe.stdout.strip()).resolve() == repo
    assert _git(repo, "rev-parse", "HEAD").returncode == 0
    monkeypatch.chdir(repo)
    monkeypatch.setenv("ORKET_REPLAY_ARTIFACTS", "1")
    return repo


def _commit(repo):
    assert _git(repo, "add", "-A").returncode == 0
    assert _git(repo, "commit", "-m", "native refusal fixture").returncode == 0


def _no_repository(path, monkeypatch):
    # Native Git must not discover an outer checkout when pytest basetemp is inside it.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(path.resolve().parent))
    probe = _git(path, "rev-parse", "--show-toplevel")
    assert probe.returncode != 0 and not probe.stdout.strip()
    monkeypatch.chdir(path)
    monkeypatch.setenv("ORKET_REPLAY_ARTIFACTS", "1")


def _invoke(**changes):
    return run_api_add_transaction(**{"route_name": "member", "schema_text": "id:int,name:string",
        "method": "post", "scope_inputs": ["src"], "dry_run": False, "auto_confirm": True, **changes})


def _assert_refused(repo, result, code):
    assert result["ok"] is False and result["code"] == code
    assert not (repo / "src/routes/member.js").exists()
    records = list((repo / ".orket/replay_artifacts/api_add").glob("*.json"))
    assert len(records) == 1
    receipt = json.loads(records[0].read_text(encoding="utf-8"))
    assert receipt["result"]["code"] == code and receipt["result"]["ok"] is False


@pytest.mark.parametrize("schema", ["", "id", "id:", ":string", "9id:int"])
def test_invalid_schema_refuses_before_generated_files_and_records_result(tmp_path, monkeypatch, schema):
    repo = _prepare(tmp_path, monkeypatch)
    result = _invoke(schema_text=schema)
    _assert_refused(repo, result, "E_SCHEMA_PARSE_FAILED")


@pytest.mark.parametrize("config", ["not-json", '{}', '{"verify":{"profiles":{"default":[]}}}',
    '{"verify":{"profiles":{"default":{"commands":[]}}}}',
    '{"verify":{"profiles":{"default":{"commands":[null]}}}}',
    '{"verify":{"profiles":{"default":{"commands":[" "]}}}}'])
def test_invalid_verify_configuration_never_generates_a_draft(tmp_path, monkeypatch, config):
    repo = _prepare(tmp_path, monkeypatch)
    (repo / "orket.config.json").write_text(config, encoding="utf-8")
    _commit(repo)
    result = _invoke()
    _assert_refused(repo, result, "E_CONFIG_INVALID")
    assert (repo / "orket.config.json").read_text(encoding="utf-8") == config


@pytest.mark.parametrize("changes", [{"scope_inputs": []}, {"auto_confirm": False}])
def test_missing_scope_or_confirmation_records_refusal_without_mutation(tmp_path, monkeypatch, changes):
    repo = _prepare(tmp_path, monkeypatch)
    _assert_refused(repo, _invoke(**changes), "E_SCOPE_REQUIRED")


def test_untracked_operator_file_refuses_and_remains_intact(tmp_path, monkeypatch):
    repo = _prepare(tmp_path, monkeypatch)
    sentinel = repo / "operator.txt"
    sentinel.write_text("uncommitted operator work", encoding="utf-8")
    _assert_refused(repo, _invoke(), "E_WORKTREE_DIRTY")
    assert sentinel.read_text(encoding="utf-8") == "uncommitted operator work"


def test_missing_repository_has_only_its_refusal_receipt(tmp_path, monkeypatch):
    _no_repository(tmp_path, monkeypatch)
    _assert_refused(tmp_path, _invoke(), "E_GIT_REQUIRED")
    assert not (tmp_path / "src").exists()


def test_unsupported_project_is_not_guessed_into_an_express_layout(tmp_path, monkeypatch):
    repo = _prepare(tmp_path, monkeypatch)
    (repo / "src/routes/index.js").unlink()
    _commit(repo)
    _assert_refused(repo, _invoke(), "E_PROJECT_STYLE_UNSUPPORTED")


def _unborn_repo(tmp_path, monkeypatch):
    repo = (tmp_path / "unborn").resolve()
    assert repo.is_relative_to(tmp_path.resolve())
    repo.mkdir()
    assert _git(repo, "init").returncode == 0
    (repo / ".git/info/exclude").write_text("*\n", encoding="utf-8")
    (repo / "orket.config.json").write_text(json.dumps({"verify": {"profiles": {
        "default": {"commands": ["python -V"]}}}}), encoding="utf-8")
    assert _git(repo, "status", "--porcelain").stdout == ""
    monkeypatch.chdir(repo)
    monkeypatch.setenv("ORKET_REPLAY_ARTIFACTS", "1")
    return repo


def test_unborn_head_cannot_enter_the_mutating_transaction(tmp_path, monkeypatch):
    repo = _unborn_repo(tmp_path, monkeypatch)
    (repo / "src/routes").mkdir(parents=True)
    (repo / "src/routes/index.js").write_text("module.exports = router;\n", encoding="utf-8")
    result = _invoke()
    _assert_refused(repo, result, "E_INTERNAL")
    assert result["message"] == "Unable to resolve git HEAD."


def test_native_directory_conflict_rolls_back_without_destroying_retained_file(tmp_path, monkeypatch):
    repo = _prepare(tmp_path, monkeypatch)
    controller = repo / "src/controllers"
    controller.rmdir()
    controller.write_text("retained file, not a directory", encoding="utf-8")
    _commit(repo)
    head = _git(repo, "rev-parse", "HEAD").stdout
    _assert_refused(repo, _invoke(), "E_INTERNAL")
    assert controller.read_text(encoding="utf-8") == "retained file, not a directory"
    assert _git(repo, "rev-parse", "HEAD").stdout == head
    assert _git(repo, "diff", "--exit-code", "HEAD").returncode == 0


def test_native_failed_verification_retains_bounded_tail_and_restores_checkout(tmp_path, monkeypatch):
    repo = _prepare(tmp_path, monkeypatch)
    monkeypatch.setenv("ORKET_FAILURE_LESSONS", "1")
    (repo / "verify.py").write_text(
        "import sys\nprint('BEGIN-EXCLUDED')\nprint(('x' * 300 + '\\n') * 400)\n"
        "print('END-RETAINED')\nsys.exit(7)\n", encoding="utf-8")
    _commit(repo)
    head = _git(repo, "rev-parse", "HEAD").stdout
    result = _invoke()
    _assert_refused(repo, result, "E_DRAFT_FAILURE")
    assert result["verify_exit_code"] == 7
    tail = result["verify_output_tail"]
    assert "END-RETAINED" in tail and "BEGIN-EXCLUDED" not in tail
    assert len(tail.splitlines()) <= 200 and len(tail.encode("utf-8")) <= 32768
    assert result["failure_lesson_id"]
    assert _git(repo, "rev-parse", "HEAD").stdout == head
    assert _git(repo, "diff", "--exit-code", "HEAD").returncode == 0


def test_partial_existing_route_preserves_operator_controller_and_types(tmp_path, monkeypatch):
    repo = _prepare(tmp_path, monkeypatch)
    index = repo / "src/routes/index.js"
    index.write_text("const router = {};\n", encoding="utf-8")
    controller = repo / "src/controllers/member_controller.js"
    controller.write_text("module.exports = operatorHandler;\n", encoding="utf-8")
    types = repo / "src/types/member.json"
    types.write_text('{"operator_schema":true}\n', encoding="utf-8")
    _commit(repo)
    result = _invoke()
    assert result["ok"] and not result.get("idempotent")
    assert controller.read_text(encoding="utf-8") == "module.exports = operatorHandler;\n"
    assert types.read_text(encoding="utf-8") == '{"operator_schema":true}\n'
    assert index.read_text(encoding="utf-8").endswith("registerMemberRoute(router);\n")
    assert "router.post('/member', handleMemberPost);" in (repo / "src/routes/member.js").read_text(encoding="utf-8")
