"""Independent processes own admission, preserve interrupted intent and reap children."""
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

import orket
from orket.core.contracts.protocol_error_codes import is_registered_protocol_error_code

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("database", ["a.db", "b.db"])
@pytest.mark.parametrize("abrupt", [False, True])
def test_native_owner_contention_and_recovery(tmp_path, database, abrupt):
    """Layer: integration. Native ownership fences shared SQLite or protocol storage."""
    worker = Path(__file__).with_name("dual_ledger_worker.py")
    command = [sys.executable, str(worker), str(tmp_path)]
    env = dict(os.environ, ORKET_DISABLE_SANDBOX="1")
    with subprocess.Popen([*command, "a.db", "hold"], cwd=tmp_path, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as owner:
        try:
            deadline = time.monotonic() + 10
            while not (tmp_path / "owner.ready").exists():
                assert owner.poll() is None, owner.communicate()
                assert time.monotonic() < deadline, "owner did not reach durable admission"
                time.sleep(0.01)
            with sqlite3.connect((tmp_path / "a.db").as_uri() + "?mode=ro", uri=True) as connection:
                assert connection.execute("SELECT run_name FROM run_ledger WHERE session_id='run'").fetchone() == ("original",)
            assert not (tmp_path / "protocol" / "runs" / "run" / "events.log").exists()
            refused = subprocess.run([*command, database, "attempt"], cwd=tmp_path, env=env,
                                     capture_output=True, text=True, timeout=10)
            assert refused.returncode == 2, refused.stdout + refused.stderr
            assert json.loads(refused.stdout)["core_origin"] == str(Path(orket.__file__).resolve())
            assert "owner_busy" in json.loads(refused.stdout)["error"]
            assert is_registered_protocol_error_code(json.loads(refused.stdout)["error"])
            if abrupt:
                owner.kill()
            else:
                (tmp_path / "owner.release").write_text("release", encoding="utf-8")
        finally:
            if owner.poll() is None and not (tmp_path / "owner.release").exists():
                owner.kill()
            stdout, stderr = owner.communicate(timeout=20)
        if not abrupt:
            assert owner.returncode == 0, stdout + stderr
    # First recover the interrupted owner's exact bound journal, then admit the contender.
    for current_database in ("a.db", database):
        result = subprocess.run([*command, current_database, "attempt"], cwd=tmp_path, env=env,
                                capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stdout + result.stderr
        receipt = json.loads(result.stdout)
        assert receipt["core_origin"] == str(Path(orket.__file__).resolve())
        assert receipt["pending"] == [] and receipt["events"] == ["run_started"]
    assert owner.poll() is not None
    assert not list(tmp_path.glob(".*.tmp"))
