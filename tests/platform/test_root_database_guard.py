"""Layer: integration. Real subprocess controls for the proof database guard."""
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("relative", ["control_plane_records.sqlite3", "nested/control_plane_records.sqlite3"])
def test_database_guard_blocks_root_even_when_caller_swallows_error(tmp_path, relative):
    (tmp_path / "nested").mkdir()
    (tmp_path / "probe.py").write_text(
        "import sqlite3\n"
        "def test_probe():\n"
        "    try:\n"
        f"        with sqlite3.connect({relative!r}) as connection:\n"
        "            connection.execute('create table proof (value text)')\n"
        "    except RuntimeError:\n"
        "        pass\n",
        encoding="utf-8",
    )
    root = Path(__file__).resolve().parents[2]
    environment = dict(os.environ, PYTHONPATH=str(root), PYTEST_PLUGINS="tests.helpers.root_database_guard")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "probe.py", "-p", "no:cacheprovider"],
        cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=30,
    )
    if relative.startswith("nested/"):
        assert result.returncode == 0, result.stdout + result.stderr
        assert (tmp_path / relative).exists()
    else:
        assert result.returncode == 1, result.stdout + result.stderr
        assert "Worktree-root database guard rejected" in result.stdout
        assert not (tmp_path / relative).exists()
