"""Integration: signals during actual spawned-worker finalization retain its exit."""
from __future__ import annotations

import re
import time

import httpx
import psutil
import pytest

from tests.helpers.api_reload_process import owned_server, signal_server, until
from tests.integration.test_api_server_reload import environment, health, trigger_reload

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("stop", ["shutdown", "reload"])
@pytest.mark.parametrize("failure", [False, True])
def test_reload_signals_retain_worker_through_process_finalization(tmp_path, stop, failure, record_property):
    values, port = environment(tmp_path, controlled=True, RELOAD_TEST_FINALIZER="fail" if failure else "ok")
    with owned_server(tmp_path, [], values) as process, httpx.Client(
        base_url=f"http://127.0.0.1:{port}", timeout=1, trust_env=False,
    ) as client:
        worker_pid = until(lambda: health(client))["pid"]
        worker = psutil.Process(worker_pid)
        identity = {"pid": worker_pid, "created": worker.create_time()}
        try:
            if stop == "reload":
                trigger_reload(tmp_path, 1)
            else:
                signal_server(process, tmp_path / "server.py")
            until(lambda: (tmp_path / f"{worker_pid}-process-finalization-held").exists())
            assert (tmp_path / f"{worker_pid}-closed").exists()
            for _ in range(2):
                signal_server(process, tmp_path / "server.py")
                time.sleep(0.15)
                assert process.poll() is None and worker.is_running()
                assert not (tmp_path / f"{worker_pid}-process-finalization-done").exists()
        finally:
            (tmp_path / "release-finalizer").touch()
        assert process.wait(timeout=15) == (1 if failure else 0)
        assert (tmp_path / f"{worker_pid}-process-finalization-done").exists()
        assert not worker.is_running()
        record_property("retained_worker_identity", str(identity))
    log = (tmp_path / "server.log").read_text(encoding="utf-8")
    assert len(re.findall(r"Started server process \[(\d+)\]", log)) == 1
    assert log.count("Application shutdown complete.") == 1
    if failure:
        assert "E_API_RELOAD_WORKER_FAILED: 17" in log
    else:
        assert "E_API_RELOAD_WORKER_FAILED" not in log
