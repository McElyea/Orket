from __future__ import annotations

# Layer: unit
import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType


def _load_project_dump_module() -> ModuleType:
    module_path = Path("project_dump.py")
    spec = importlib.util.spec_from_file_location("project_dump_test_module", module_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_project_dump_respects_gitignored_files(tmp_path: Path) -> None:
    """Layer: unit. Verifies the dump inventory follows git ignore rules and excludes ignored local config files."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    (repo / ".gitignore").write_text(".claude/\n", encoding="utf-8")
    (repo / "visible.py").write_text("print('visible')\n", encoding="utf-8")
    (repo / ".claude").mkdir()
    (repo / ".claude" / "settings.local.json").write_text('{"secret": true}\n', encoding="utf-8")

    module = _load_project_dump_module()
    module.export_project_review_packet(root_dir=str(repo), output_file="dump.txt")

    dump_text = (repo / "dump.txt").read_text(encoding="utf-8")
    assert "visible.py" in dump_text
    assert ".claude/settings.local.json" not in dump_text
