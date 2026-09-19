from __future__ import annotations

# Layer: unit
import runpy

import pytest


@pytest.mark.unit
def test_main_logs_crash_and_exits(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path) -> None:
    """Layer: unit. Verifies the CLI crash handler logs once and exits cleanly on fatal startup errors."""

    def _fake_create_cli_runtime():
        async def _runner(*_args, **_kwargs) -> None:
            raise RuntimeError("boom")

        return _runner

    captured: dict[str, object] = {}

    async def _fake_publish(self, exc: Exception, tb: str):
        captured["exc"] = exc
        captured["tb"] = tb
        return tmp_path / "orket_crash.log"

    monkeypatch.setattr("orket.interfaces.runtime_entrypoints.create_cli_runtime", _fake_create_cli_runtime)
    monkeypatch.setattr("orket.application.services.crash_report_service.CrashReportService.publish", _fake_publish)

    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("main", run_name="__main__")

    output = capsys.readouterr().out
    assert excinfo.value.code == 1
    assert isinstance(captured["exc"], RuntimeError)
    assert "boom" in str(captured["exc"])
    assert "RuntimeError: boom" in str(captured["tb"])
    assert "[CRITICAL ERROR] Orket CLI crashed: boom" in output


# Layer: unit
@pytest.mark.unit
def test_main_interrupt_exits_with_signal_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: unit. Verifies an interrupt outside the async CLI boundary cannot become process success."""

    def _interrupt() -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("orket.settings.load_env", _interrupt)

    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("main", run_name="__main__")

    assert excinfo.value.code == 130
