"""Contract: native process receipt classification is strict and deterministic."""

from typing import Any

import psutil
import pytest

import tests.helpers.log_process_receipts as process_receipts

pytestmark = pytest.mark.contract


class _FakeProcess:
    def __init__(self, outcome: object) -> None:
        self._outcome = outcome

    def create_time(self) -> float:
        if isinstance(self._outcome, BaseException):
            raise self._outcome
        return self._outcome  # type: ignore[return-value]


def _install_fake_process(
    monkeypatch: pytest.MonkeyPatch,
    outcomes: dict[int, object],
) -> list[int]:
    calls: list[int] = []

    def process(pid: int) -> _FakeProcess:
        calls.append(pid)
        return _FakeProcess(outcomes[pid])

    monkeypatch.setattr(process_receipts.psutil, "Process", process)
    return calls


# Layer: contract
@pytest.mark.parametrize(
    ("expected_created", "outcome", "status"),
    [
        (None, psutil.NoSuchProcess(41), "absent"),
        (10.0, 11.0, "reused"),
        (None, 10.0, "present_unknown"),
        (10.0, 10, "present_same"),
        (10, 10.0, "present_same"),
    ],
)
def test_process_readback_classifies_valid_states(
    monkeypatch: pytest.MonkeyPatch,
    expected_created: float | None,
    outcome: object,
    status: str,
) -> None:
    calls = _install_fake_process(monkeypatch, {41: outcome})

    observed = process_receipts.process_readback({41: expected_created})

    expected: dict[str, Any] = {"status": status, "expected_create_time": expected_created}
    if status != "absent":
        expected["actual_create_time"] = outcome
    assert observed == {"41": expected}
    assert calls == [41]


# Layer: contract
@pytest.mark.parametrize(
    "error",
    [psutil.ZombieProcess(41), psutil.AccessDenied(41), RuntimeError("unexpected")],
    ids=["zombie", "access-denied", "unexpected"],
)
def test_process_readback_propagates_non_absence_errors(
    monkeypatch: pytest.MonkeyPatch,
    error: BaseException,
) -> None:
    calls = _install_fake_process(monkeypatch, {41: error})

    with pytest.raises(type(error)) as raised:
        process_receipts.process_readback({41: 10.0})

    assert raised.value is error
    assert calls == [41]


# Layer: contract
@pytest.mark.parametrize("pid", [0, -1, True, 1.5, "41", None])
def test_process_readback_refuses_invalid_pid_without_lookup(
    monkeypatch: pytest.MonkeyPatch,
    pid: object,
) -> None:
    calls = _install_fake_process(monkeypatch, {})

    with pytest.raises(ValueError, match="^E_PROCESS_READBACK_PID_INVALID$"):
        process_receipts.process_readback({pid: None})  # type: ignore[dict-item]

    assert calls == []


# Layer: contract
@pytest.mark.parametrize("created", [0, -1, True, float("nan"), float("inf"), "10"])
def test_process_readback_refuses_invalid_expected_creation_without_lookup(
    monkeypatch: pytest.MonkeyPatch,
    created: object,
) -> None:
    calls = _install_fake_process(monkeypatch, {})

    with pytest.raises(ValueError, match="^E_PROCESS_READBACK_EXPECTED_CREATION_INVALID$"):
        process_receipts.process_readback({41: created})  # type: ignore[dict-item]

    assert calls == []


# Layer: contract
@pytest.mark.parametrize("created", [0, -1, True, float("nan"), float("inf"), "10", None])
def test_process_readback_refuses_invalid_observed_creation(
    monkeypatch: pytest.MonkeyPatch,
    created: object,
) -> None:
    calls = _install_fake_process(monkeypatch, {41: created})

    with pytest.raises(ValueError, match="^E_PROCESS_READBACK_OBSERVED_CREATION_INVALID$"):
        process_receipts.process_readback({41: 10.0})

    assert calls == [41]
