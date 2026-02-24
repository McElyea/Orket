from __future__ import annotations

import json
import subprocess
from pathlib import Path

from orket.interfaces.orket_bundle_cli import main


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)


def _write_verify_harness(repo: Path) -> None:
    verify_script = repo / "verify.py"
    verify_script.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "sys.exit(1 if Path('tests/SHOULD_FAIL').exists() else 0)\n",
        encoding="utf-8",
    )
    config = {
        "verify": {
            "profiles": {
                "default": {
                    "commands": ["python verify.py"],
                }
            }
        }
    }
    (repo / "orket.config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")


def _init_express_fixture(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "orket-test@example.com")
    _git(repo, "config", "user.name", "Orket Test")

    routes_dir = repo / "src" / "routes"
    routes_dir.mkdir(parents=True, exist_ok=True)
    (routes_dir / "index.js").write_text(
        "const express = require('express');\n"
        "const router = express.Router();\n\n"
        "module.exports = router;\n",
        encoding="utf-8",
    )
    (repo / "src" / "controllers").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "types").mkdir(parents=True, exist_ok=True)
    (repo / "tests").mkdir(parents=True, exist_ok=True)
    _write_verify_harness(repo)

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial express fixture")
    return repo


def test_api_add_deterministic_output_and_idempotent_rerun(tmp_path: Path, capsys, monkeypatch) -> None:
    repo = _init_express_fixture(tmp_path)
    monkeypatch.chdir(repo)

    code_first = main(
        [
            "api",
            "add",
            "member",
            "--schema",
            "id:int,name:string",
            "--scope",
            "./src",
            "--yes",
        ]
    )
    out_first = capsys.readouterr().out
    assert code_first == 0
    assert "API route generated." in out_first

    route_before = (repo / "src" / "routes" / "member.js").read_text(encoding="utf-8")
    controller_before = (repo / "src" / "controllers" / "member_controller.js").read_text(encoding="utf-8")
    types_before = (repo / "src" / "types" / "member.json").read_text(encoding="utf-8")
    routes_index_before = (repo / "src" / "routes" / "index.js").read_text(encoding="utf-8")

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add member route")

    code_second = main(
        [
            "api",
            "add",
            "member",
            "--schema",
            "id:int,name:string",
            "--scope",
            "./src",
            "--yes",
        ]
    )
    out_second = capsys.readouterr().out
    assert code_second == 0
    assert "Idempotent no-op" in out_second
    assert (repo / "src" / "routes" / "member.js").read_text(encoding="utf-8") == route_before
    assert (repo / "src" / "controllers" / "member_controller.js").read_text(encoding="utf-8") == controller_before
    assert (repo / "src" / "types" / "member.json").read_text(encoding="utf-8") == types_before
    assert (repo / "src" / "routes" / "index.js").read_text(encoding="utf-8") == routes_index_before
    assert _git(repo, "status", "--porcelain").stdout.strip() == ""


def test_api_add_preserves_extension_region_on_rerun(tmp_path: Path, capsys, monkeypatch) -> None:
    repo = _init_express_fixture(tmp_path)
    monkeypatch.chdir(repo)
    assert main(["api", "add", "member", "--schema", "id:int,name:string", "--scope", "./src", "--yes"]) == 0
    _ = capsys.readouterr()

    controller = repo / "src" / "controllers" / "member_controller.js"
    text = controller.read_text(encoding="utf-8")
    text = text.replace(
        "return res.status(501).json({ message: 'Implement route handler logic.' });",
        "return res.status(200).json({ ok: true });",
    )
    controller.write_text(text, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "customize extension region")

    assert main(["api", "add", "member", "--schema", "id:int,name:string", "--scope", "./src", "--yes"]) == 0
    _ = capsys.readouterr()
    assert "res.status(200).json({ ok: true });" in controller.read_text(encoding="utf-8")


def test_api_add_verify_failure_reverts_repo(tmp_path: Path, capsys, monkeypatch) -> None:
    repo = _init_express_fixture(tmp_path)
    (repo / "tests" / "SHOULD_FAIL").write_text("force fail\n", encoding="utf-8")
    _git(repo, "add", "tests/SHOULD_FAIL")
    _git(repo, "commit", "-m", "force verify fail marker")
    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()

    monkeypatch.chdir(repo)
    code = main(["api", "add", "member", "--schema", "id:int,name:string", "--scope", "./src", "--yes"])
    out = capsys.readouterr().out

    assert code == 1
    assert "E_DRAFT_FAILURE" in out
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == head_before
    assert _git(repo, "status", "--porcelain").stdout.strip() == ""
    assert not (repo / "src" / "routes" / "member.js").exists()


def test_api_add_scope_barrier_blocks_out_of_scope_writes(tmp_path: Path, capsys, monkeypatch) -> None:
    repo = _init_express_fixture(tmp_path)
    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    monkeypatch.chdir(repo)

    code = main(["api", "add", "member", "--schema", "id:int,name:string", "--scope", "./src/routes", "--yes"])
    out = capsys.readouterr().out

    assert code == 1
    assert "E_WRITE_OUT_OF_SCOPE" in out
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == head_before
    assert _git(repo, "status", "--porcelain").stdout.strip() == ""


def test_api_add_dry_run_outputs_touch_set(tmp_path: Path, capsys, monkeypatch) -> None:
    repo = _init_express_fixture(tmp_path)
    monkeypatch.chdir(repo)

    code = main(["api", "add", "member", "--schema", "id:int,name:string", "--scope", "./src", "--dry-run"])
    out = capsys.readouterr().out

    assert code == 0
    assert "FILES TO BE MODIFIED" in out
    assert "src/routes/member.js" in out
    assert "src/controllers/member_controller.js" in out
    assert "src/types/member.json" in out
