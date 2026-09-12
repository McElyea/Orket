# Layer: end-to-end; real local provider, API process exit, durable effects and restarted API
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from orket.runtime.config.defaults import DEFAULT_LOCAL_MODEL
from orket_extension_sdk.agent_testing import ticket_report_fixture
from tests.e2e.test_governed_agent_supervisor_ollama import _configure_api, _write_catalog


@pytest.mark.end_to_end
@pytest.mark.skipif(not any(os.getenv(key) == "1" for key in
    ("ORKET_RUN_LIVE_AGENT_LLAMA_CPP", "ORKET_RUN_LIVE_AGENT_OLLAMA")), reason="requires live local provider")
@pytest.mark.parametrize("point", ["before_write", "after_write"])
def test_abrupt_api_exit_recovers_without_repeating_write(tmp_path, monkeypatch, point):
    """Layer: end-to-end. Two real API processes exercise pre/post-write crash windows."""
    llama = os.getenv("ORKET_RUN_LIVE_AGENT_LLAMA_CPP") == "1"
    model = os.getenv("ORKET_GOVERNED_AGENT_MODEL", DEFAULT_LOCAL_MODEL)
    _configure_api(monkeypatch, db_path=tmp_path / "agent.sqlite3", catalog_path=_write_catalog(tmp_path),
                   planner=model if llama else "qwen2.5:7b", actor=model if llama else "qwen2.5-coder:7b",
                   critic=model if llama else "qwen2.5:7b", provider="llama_cpp" if llama else "ollama")
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
