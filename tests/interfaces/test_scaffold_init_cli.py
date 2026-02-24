from __future__ import annotations

import hashlib
from pathlib import Path

from orket.interfaces.orket_bundle_cli import main
import orket.interfaces.scaffold_init as scaffold_init_module


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix().encode("utf-8")
            digest.update(rel)
            digest.update(path.read_bytes())
    return digest.hexdigest()


def test_init_generates_deterministic_blueprint_output(tmp_path: Path, capsys, monkeypatch) -> None:
    out_one = tmp_path / "one"
    out_two = tmp_path / "two"
    monkeypatch.chdir(tmp_path)

    code_one = main(["init", "minimal-node", "demo", "--dir", str(out_one), "--json"])
    payload_one = capsys.readouterr().out
    code_two = main(["init", "minimal-node", "demo", "--dir", str(out_two), "--json"])
    payload_two = capsys.readouterr().out

    assert code_one == 0
    assert code_two == 0
    assert '"ok": true' in payload_one.lower()
    assert '"ok": true' in payload_two.lower()
    assert _tree_hash(out_one) == _tree_hash(out_two)


def test_init_verify_failure_removes_output_dir(tmp_path: Path, capsys, monkeypatch) -> None:
    out_dir = tmp_path / "broken"
    monkeypatch.chdir(tmp_path)

    original = scaffold_init_module._builtin_blueprints

    def _failing_blueprint():
        blueprints = original()
        bp = blueprints["minimal-node"]
        blueprints["minimal-node"] = scaffold_init_module.Blueprint(
            name=bp.name,
            verify_commands=["python -c \"import sys; sys.exit(1)\""],
            templates=bp.templates,
        )
        return blueprints

    monkeypatch.setattr(scaffold_init_module, "_builtin_blueprints", _failing_blueprint)

    code = main(["init", "minimal-node", "demo", "--dir", str(out_dir)])
    out = capsys.readouterr().out

    assert code == 1
    assert "E_INIT_VERIFY_FAILED" in out
    assert not out_dir.exists()


def test_init_fails_if_output_directory_exists(tmp_path: Path, capsys, monkeypatch) -> None:
    out_dir = tmp_path / "demo"
    out_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)

    code = main(["init", "minimal-node", "demo", "--dir", str(out_dir)])
    out = capsys.readouterr().out

    assert code == 1
    assert "E_OUTPUT_DIR_EXISTS" in out
