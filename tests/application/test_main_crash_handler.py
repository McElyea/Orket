from __future__ import annotations

# Layer: unit
import runpy

import pytest


def test_main_logs_crash_and_exits(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Layer: unit. Verifies the CLI crash handler logs once and exits cleanly on fatal startup errors."""

    def _fake_create_cli_runtime():
        async def _runner() -> None:
            raise RuntimeError("boom")

        return _runner

    captured: dict[str, object] = {}

    def _fake_log_crash(exc: Exception, tb: str) -> None:
        captured["exc"] = exc
        captured["tb"] = tb

    monkeypatch.setattr("orket.runtime.create_cli_runtime", _fake_create_cli_runtime)
    monkeypatch.setattr("orket.logging.log_crash", _fake_log_crash)

    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("main", run_name="__main__")

    output = capsys.readouterr().out
    assert excinfo.value.code == 1
    assert isinstance(captured["exc"], RuntimeError)
    assert "boom" in str(captured["exc"])
    assert "RuntimeError: boom" in str(captured["tb"])
    assert "[CRITICAL ERROR] Orket CLI crashed: boom" in output
