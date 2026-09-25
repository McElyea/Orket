# LIFECYCLE: contract
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from scripts.security import build_tool_gate_audit as audit_module

pytestmark = pytest.mark.contract
_EXISTING_NOTE = "existing primary note"
_DAEMON_DETAIL = "private daemon detail"
_EXPECTED_NOTE = (
    "Audit log settlement failed: code=E_LOG_WRITER_TERMINATED; "
    "secondary_type=RuntimeError; daemon_cause_type=ValueError"
)


class _SameTextRuntimeError(RuntimeError):
    pass


def _make_unknown_settlement(kind: str) -> BaseException:
    if kind == "same-text-runtime-subclass":
        return _SameTextRuntimeError(audit_module.LOG_WRITER_TERMINATED_ERROR)
    if kind == "wrong-runtime-arguments":
        return RuntimeError(audit_module.LOG_WRITER_TERMINATED_ERROR, "extra")
    if kind == "plain-unknown-runtime":
        return RuntimeError("E_UNKNOWN_SETTLEMENT: controlled")
    if kind == "settlement-keyboard-interrupt":
        return KeyboardInterrupt("controlled settlement interrupt")
    if kind == "settlement-system-exit":
        return SystemExit(19)
    raise AssertionError(f"Unknown settlement contract kind: {kind}")


def _install_case(
    monkeypatch: pytest.MonkeyPatch,
    state: dict[str, Any],
    *,
    primary: BaseException,
    settlement: BaseException,
) -> None:
    async def collect(temp_root: Path) -> list[dict[str, Any]]:
        state["temp_root"] = temp_root
        raise primary

    def settle() -> None:
        state["temp_root_exists_at_settlement"] = state["temp_root"].exists()
        state["primary_traceback_at_settlement"] = primary.__traceback__
        raise settlement

    def publish(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        state["published"] = True
        return {}

    monkeypatch.setattr(audit_module, "_collect_rows", collect)
    monkeypatch.setattr(audit_module, "settle_log_write_frontier", settle)
    monkeypatch.setattr(audit_module, "write_payload_with_diff_ledger", publish)


@pytest.mark.parametrize(
    "settlement_kind",
    [
        "same-text-runtime-subclass",
        "wrong-runtime-arguments",
        "plain-unknown-runtime",
        "settlement-keyboard-interrupt",
        "settlement-system-exit",
    ],
)
# Layer: contract
def test_unrecognized_settlement_keeps_normal_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    settlement_kind: str,
) -> None:
    """Layer: contract. Unknown settlement wins over the locally owned primary."""
    prior_cause = LookupError("prior cause")
    prior_context = OSError("prior context")
    primary = OSError("controlled local primary")
    primary.__cause__ = prior_cause
    primary.__context__ = prior_context
    primary.__suppress_context__ = True
    primary.add_note(_EXISTING_NOTE)
    original_graph = (primary.__cause__, primary.__context__, primary.__suppress_context__)
    settlement = _make_unknown_settlement(settlement_kind)
    state: dict[str, Any] = {"published": False}
    output = tmp_path / "must-not-publish.json"
    _install_case(monkeypatch, state, primary=primary, settlement=settlement)

    with pytest.raises(type(settlement)) as captured:
        audit_module.main(["--out", str(output), "--strict"])

    assert captured.value is settlement
    assert (primary.__cause__, primary.__context__, primary.__suppress_context__) == original_graph
    assert primary.__notes__ == [_EXISTING_NOTE]
    assert not getattr(settlement, "__notes__", ())
    assert state["temp_root_exists_at_settlement"] is True
    assert state["primary_traceback_at_settlement"] is not None
    assert state["published"] is False
    assert not output.exists()
    assert not state["temp_root"].exists()


@pytest.mark.parametrize(
    "primary_kind",
    ["primary-keyboard-interrupt", "primary-system-exit"],
)
# Layer: contract
def test_primary_interrupt_retains_graph_with_known_settlement_note(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    primary_kind: str,
) -> None:
    """Layer: contract. Exact classification preserves the existing primary graph."""
    primary: BaseException
    if primary_kind == "primary-keyboard-interrupt":
        primary = KeyboardInterrupt("controlled primary interrupt")
    else:
        primary = SystemExit(23)
    prior_cause = LookupError("prior cause")
    prior_context = OSError("prior context")
    primary.__cause__ = prior_cause
    primary.__context__ = prior_context
    primary.__suppress_context__ = True
    primary.add_note(_EXISTING_NOTE)
    original_graph = (primary.__cause__, primary.__context__, primary.__suppress_context__)

    daemon = ValueError(_DAEMON_DETAIL)
    settlement = RuntimeError(audit_module.LOG_WRITER_TERMINATED_ERROR)
    settlement.__cause__ = daemon
    settlement.__suppress_context__ = True
    state: dict[str, Any] = {"published": False}
    output = tmp_path / "must-not-publish.json"
    _install_case(monkeypatch, state, primary=primary, settlement=settlement)

    with pytest.raises(type(primary)) as captured:
        audit_module.main(["--out", str(output), "--strict"])

    assert captured.value is primary
    assert (primary.__cause__, primary.__context__, primary.__suppress_context__) == original_graph
    assert primary.__notes__ == [_EXISTING_NOTE, _EXPECTED_NOTE]
    assert _DAEMON_DETAIL not in primary.__notes__[-1]
    assert state["temp_root_exists_at_settlement"] is True
    assert state["primary_traceback_at_settlement"] is not None
    assert state["published"] is False
    assert not output.exists()
    assert not state["temp_root"].exists()
