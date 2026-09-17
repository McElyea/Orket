"""Independent native processes share one retained operation-commit authority."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from orket.adapters.storage.operation_commit_registry import OperationCommitRegistry
from orket.core.contracts.protocol_error_codes import is_registered_protocol_error_code

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("contender_id", ["op-first", "op-second"])
# Layer: integration
def test_native_registry_contention_and_retry_preserve_first_commit(tmp_path, contender_id):
    path = tmp_path / "operation_commits.json"
    worker = Path(__file__).with_name("protocol_registry_worker.py")
    env = dict(os.environ, ORKET_DISABLE_SANDBOX="1")
    arguments = [sys.executable, str(worker), str(path)]
    with subprocess.Popen([*arguments, "op-first", "a" * 64, "hold"], env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as owner:
        try:
            deadline = time.monotonic() + 10
            while not Path(str(path) + ".ready").exists():
                assert owner.poll() is None, owner.communicate()
                assert time.monotonic() < deadline
                time.sleep(0.01)
            contender = subprocess.run([*arguments, contender_id, "b" * 64, "immediate"], env=env,
                                       capture_output=True, text=True, timeout=10)
            assert contender.returncode == 2, contender.stdout + contender.stderr
            refused = json.loads(contender.stdout)
            assert refused["status"] == "busy" and "owner_busy" in refused["error"]
            assert is_registered_protocol_error_code(refused["error"])
            assert not path.exists()
        finally:
            Path(str(path) + ".release").write_text("release", encoding="utf-8")
            stdout, stderr = owner.communicate(timeout=20)
        assert owner.returncode == 0, stdout + stderr
        assert json.loads(stdout)["accepted"]
    retry = subprocess.run([*arguments, contender_id, "b" * 64, "immediate"], env=env,
                           capture_output=True, text=True, timeout=10)
    assert retry.returncode == 0, retry.stdout + retry.stderr
    decision = json.loads(retry.stdout)
    assert decision["accepted"] is (contender_id == "op-second")
    fresh = OperationCommitRegistry(path)
    assert fresh.winner("op-first")["entry_digest"] == "a" * 64
    assert len(fresh.entries()) == (2 if contender_id == "op-second" else 1)
    assert not list(tmp_path.glob(".operation_commits.json.*.tmp"))
