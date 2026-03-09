from __future__ import annotations

import json
from pathlib import Path

from orket.interfaces.orket_bundle_cli import main


def test_ext_init_scaffolds_template_repo(tmp_path: Path, capsys) -> None:
    """Layer: integration. Verifies `orket ext init` materializes the canonical external-extension template."""
    target = tmp_path / "companion_ext"
    code = main(["ext", "init", str(target), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["ok"] is True
    assert target.joinpath("extension.yaml").is_file()
    assert target.joinpath("pyproject.toml").is_file()
    assert target.joinpath(".gitea", "workflows", "ci.yml").is_file()
    assert target.joinpath("src", "companion_app", "server.py").is_file()
    assert target.joinpath("src", "companion_app", "static", "index.html").is_file()
    assert target.joinpath("src", "companion_app", "static", "app.js").is_file()
    assert target.joinpath("src", "companion_app", "static", "styles.css").is_file()


def test_ext_init_fails_when_target_exists_without_force(tmp_path: Path, capsys) -> None:
    """Layer: contract. Verifies `orket ext init` fails closed when target already exists."""
    target = tmp_path / "companion_ext"
    target.mkdir(parents=True, exist_ok=True)
    code = main(["ext", "init", str(target), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 2
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "E_EXT_TARGET_EXISTS"
