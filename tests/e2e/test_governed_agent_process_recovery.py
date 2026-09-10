# Layer: end-to-end; real Ollama, API process exit, durable effects and restarted API
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from orket_extension_sdk.agent_testing import ticket_report_fixture
from tests.e2e.test_governed_agent_supervisor_ollama import _configure_api, _write_catalog


@pytest.mark.end_to_end
@pytest.mark.skipif(os.getenv("ORKET_RUN_LIVE_AGENT_OLLAMA") != "1", reason="requires live Ollama")
@pytest.mark.parametrize("point", ["before_write", "after_write"])
def test_abrupt_api_exit_recovers_without_repeating_write(tmp_path, monkeypatch, point):
    """Layer: end-to-end. Two real API processes exercise pre/post-write crash windows."""
    _configure_api(monkeypatch, db_path=tmp_path / "agent.sqlite3", catalog_path=_write_catalog(tmp_path),
                   planner="qwen2.5:7b", actor="qwen2.5-coder:7b", critic="qwen2.5:7b")
    source = tmp_path / "inputs/tickets.json"
    source.parent.mkdir()
    source.write_text(json.dumps(ticket_report_fixture()["batches"]), encoding="utf-8")
    worker = Path(__file__).with_name("governed_agent_process_worker.py")
    for mode, expected in (("crash", 93), ("recover", 0)):
        result = subprocess.run([sys.executable, str(worker), str(tmp_path), mode, point],
                                capture_output=True, text=True, timeout=240, check=False)
        (tmp_path / f"{mode}.log").write_text(result.stdout + result.stderr, encoding="utf-8")
        assert result.returncode == expected, result.stdout + result.stderr
        print(result.stdout)
