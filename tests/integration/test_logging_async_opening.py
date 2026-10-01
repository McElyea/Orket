"""Layer: integration. Optional logging must not block independent SQLite work."""
import json
import logging
import threading
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

import pytest

from orket.adapters.observability.logging_context import bind_logging, prepare_logging
from orket.core.contracts.logging_inputs import LoggingInputs
from orket.logging import (
    event_subscriber_count,
    log_event,
    subscribe_to_events,
    unsubscribe_from_events,
)
from tests.helpers.logging_async_opening import (
    HOLD_SECONDS,
    HeldStandardHandler,
    HoldState,
    LogObservation,
    held_subscriber,
    hold_path_stage,
    join_fixture_thread,
    observe_log_call,
    start_fixture_thread,
    wait_for_event_records,
    wait_for_fixture_event,
    wait_for_stage_entry,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _result_summary(result: object) -> object:
    if isinstance(result, BaseException):
        return {"exception": repr(result)}
    return result


def _record_observation(
    record_property: Any,
    name: str,
    observation: LogObservation,
    state: HoldState,
    extra: dict[str, Any] | None = None,
) -> None:
    payload = {
        "log_result": _result_summary(observation.log_result),
        "sqlite_result": _result_summary(observation.sqlite_result),
        "physical_records": observation.records,
        "loop_thread": observation.loop_thread,
        "stage_worker": state.worker,
        "stage_calls": state.calls,
        "stage_entered": state.entered.is_set(),
        "stage_finished": observation.stage_finished,
        "hold_expired": state.expired,
        "watchdog_auto_released": state.auto_released,
        "watchdog_error": state.watchdog_error,
        "watchdog_finished": state.watchdog_finished.is_set(),
        "watchdog_alive": observation.watchdog_alive,
        "timed_out": observation.timed_out,
        **(extra or {}),
    }
    record_property(name, json.dumps(payload, default=str, sort_keys=True))


def _assert_common(observation: LogObservation, state: HoldState, event: str) -> None:
    assert not observation.timed_out
    assert isinstance(observation.log_result, dict)
    assert isinstance(observation.sqlite_result, dict)
    assert observation.sqlite_result["row"] == (42,)
    assert observation.stage_finished
    assert state.entered.is_set()
    assert state.finished.is_set()
    assert state.calls == 1
    assert not state.expired
    assert state.auto_released
    assert state.watchdog_error is None
    assert state.watchdog_finished.is_set()
    assert not observation.watchdog_alive
    assert [record["event"] for record in observation.records] == [event]


def _assert_responsive(observation: LogObservation, state: HoldState) -> None:
    assert 0 < observation.sqlite_result["elapsed"] < 0.5
    assert 0 < observation.log_result["elapsed"] < 0.5
    assert state.worker != observation.loop_thread


def _nested_subscriber(
    event: str,
    records: list[dict[str, Any]],
    observed: threading.Event,
) -> Callable[[dict[str, Any]], None]:
    def subscriber(record: dict[str, Any]) -> None:
        if record.get("event") == event:
            records.append(json.loads(json.dumps(record, default=str)))
            observed.set()

    return subscriber


def _mutate_nested(
    state: HoldState,
    payload: dict[str, Any],
    mutated: threading.Event,
) -> None:
    if wait_for_stage_entry(state):
        payload["nested"]["values"].append("late")
        mutated.set()


@pytest.mark.parametrize("stage", ["resolve", "mkdir"])
async def test_async_optional_log_keeps_sqlite_responsive_during_first_path_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Any,
    stage: str,
) -> None:
    prepared = await prepare_logging(LoggingInputs(tmp_path))
    with bind_logging(prepared):
        event = f"logging_opening_path_{stage}"
        workspace = tmp_path / f"workspace_{stage}"
        state = hold_path_stage(monkeypatch, workspace, stage)

        observation = await observe_log_call(
            log=log_event,
            event=event,
            payload={"stage": stage},
            workspace=workspace,
            state=state,
        )

        _record_observation(record_property, f"{stage}_observation", observation, state)
        _assert_common(observation, state, event)
        _assert_responsive(observation, state)


async def test_async_optional_log_keeps_sqlite_responsive_during_standard_handler(
    tmp_path: Path,
    record_property: Any,
) -> None:
    prepared = await prepare_logging(LoggingInputs(tmp_path))
    with bind_logging(prepared):
        event = "logging_opening_standard_handler"
        workspace = tmp_path / "handler_workspace"
        state = HoldState()
        handler = HeldStandardHandler(state, event)
        logger = logging.getLogger("orket")
        logger.addHandler(handler)
        try:
            observation = await observe_log_call(
                log=log_event,
                event=event,
                payload={"sink": "standard_handler"},
                workspace=workspace,
                state=state,
            )
        finally:
            state.release.set()
            logger.removeHandler(handler)
            handler.close()

        _record_observation(record_property, "handler_observation", observation, state)
        _assert_common(observation, state, event)
        _assert_responsive(observation, state)


async def test_async_optional_log_keeps_sqlite_responsive_during_subscriber(
    tmp_path: Path,
    record_property: Any,
) -> None:
    prepared = await prepare_logging(LoggingInputs(tmp_path))
    with bind_logging(prepared):
        event = "logging_opening_subscriber"
        workspace = tmp_path / "subscriber_workspace"
        state = HoldState()
        subscriber = held_subscriber(state, event)
        baseline = event_subscriber_count()
        subscribe_to_events(subscriber)
        try:
            observation = await observe_log_call(
                log=log_event,
                event=event,
                payload={"sink": "subscriber"},
                workspace=workspace,
                state=state,
            )
        finally:
            state.release.set()
            unsubscribe_from_events(subscriber)
        restored_count = event_subscriber_count()

        _record_observation(
            record_property,
            "subscriber_observation",
            observation,
            state,
            {"subscriber_records": state.records, "restored_count": restored_count},
        )
        _assert_common(observation, state, event)
        assert len(state.records) == 1
        assert restored_count == baseline
        _assert_responsive(observation, state)


async def test_async_optional_log_captures_nested_payload_before_held_processing(
    tmp_path: Path,
    record_property: Any,
) -> None:
    prepared = await prepare_logging(LoggingInputs(tmp_path))
    with bind_logging(prepared):
        event = "logging_opening_nested_capture"
        workspace = tmp_path / "nested_workspace"
        payload = {"nested": {"values": ["captured"]}}
        state = HoldState()
        handler = HeldStandardHandler(state, event)
        subscriber_records: list[dict[str, Any]] = []
        subscriber_observed = threading.Event()
        mutated = threading.Event()
        subscriber = _nested_subscriber(event, subscriber_records, subscriber_observed)
        logger = logging.getLogger("orket")
        mutator = threading.Thread(
            target=partial(_mutate_nested, state, payload, mutated),
            name="orket-logging-opening-mutator",
            daemon=False,
        )
        logger.addHandler(handler)
        subscribe_to_events(subscriber)
        subscriber_finished = False
        try:
            await start_fixture_thread(mutator, label="logging-opening-mutator")
            observation = await observe_log_call(
                log=log_event,
                event=event,
                payload=payload,
                workspace=workspace,
                state=state,
            )
            subscriber_finished = await wait_for_fixture_event(
                subscriber_observed,
                label="logging-opening-subscriber-observed",
            )
        finally:
            state.release.set()
            try:
                unsubscribe_from_events(subscriber)
                logger.removeHandler(handler)
                handler.close()
            finally:
                await join_fixture_thread(mutator, label="logging-opening-mutator")

        _record_observation(
            record_property,
            "nested_capture_observation",
            observation,
            state,
            {
                "source_payload": payload,
                "subscriber_records": subscriber_records,
                "mutator_finished": not mutator.is_alive(),
                "mutated": mutated.is_set(),
                "subscriber_finished": subscriber_finished,
            },
        )
        _assert_common(observation, state, event)
        assert mutated.is_set()
        assert not mutator.is_alive()
        assert subscriber_finished
        assert payload["nested"]["values"] == ["captured", "late"]
        assert observation.records[0]["data"]["nested"]["values"] == ["captured"]
        assert len(subscriber_records) == 1
        assert subscriber_records[0]["data"]["nested"]["values"] == ["captured"]
        _assert_responsive(observation, state)


async def test_native_log_remains_inline_and_captures_before_return(
    tmp_path: Path,
    record_property: Any,
) -> None:
    event = "logging_opening_native_control"
    workspace = tmp_path / "native_workspace"
    payload = {"nested": {"values": ["captured"]}}
    state = HoldState()
    handler = HeldStandardHandler(state, event)
    logger = logging.getLogger("orket")
    logger.addHandler(handler)
    try:
        observation = await observe_log_call(
            log=log_event,
            event=event,
            payload=payload,
            workspace=workspace,
            state=state,
            native=True,
        )
    finally:
        state.release.set()
        logger.removeHandler(handler)
        handler.close()

    payload["nested"]["values"].append("after-return")
    records_after_mutation = await wait_for_event_records(workspace / "orket.log", event)
    _record_observation(
        record_property,
        "native_observation",
        observation,
        state,
        {"records_after_mutation": records_after_mutation, "source_payload": payload},
    )
    _assert_common(observation, state, event)
    assert 0 < observation.sqlite_result["elapsed"] < 0.5
    assert observation.log_result["elapsed"] >= HOLD_SECONDS
    assert state.worker == observation.log_result["thread"]
    assert state.worker != observation.loop_thread
    assert len(records_after_mutation) == 1
    assert records_after_mutation[0]["data"]["nested"]["values"] == ["captured"]
