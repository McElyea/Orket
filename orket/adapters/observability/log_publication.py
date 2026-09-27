"""One process-global owner for log queues, writer lifetime and subscribers."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import queue
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

side_effecting = True

_logger = logging.getLogger("orket")


_logger.setLevel(logging.INFO)


_LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


_prepared_log_dirs: set[Path] = set()


_prepared_log_dirs_lock = threading.Lock()


LOG_QUEUE_MAX_ENV = "ORKET_LOG_QUEUE_MAX"


DEFAULT_LOG_QUEUE_MAX = 10_000


LOG_WRITER_TERMINATED_ERROR = "E_LOG_WRITER_TERMINATED: log writer stopped before the requested frontier"


def _resolve_log_queue_max() -> int:
    try:
        configured = int(str(os.getenv(LOG_QUEUE_MAX_ENV, "")).strip())
    except ValueError:
        return DEFAULT_LOG_QUEUE_MAX
    return configured if configured > 0 else DEFAULT_LOG_QUEUE_MAX


class _LogWriteFrontier:
    def __init__(self) -> None:
        self.settled = False


_LogWriteItem = tuple[Path, str] | _LogWriteFrontier


_log_write_queue: queue.Queue[_LogWriteItem] = queue.Queue(maxsize=_resolve_log_queue_max())


_log_writer_lock = threading.Lock()


_log_writer_state = threading.Condition()


_log_writer_thread: threading.Thread | None = None


_log_writer_failure: BaseException | None = None


_dropped_log_entries = 0


_dropped_log_entries_lock = threading.Lock()


def _record_log_writer_failure(failure: BaseException) -> None:
    global _log_writer_failure
    with _log_writer_state:
        if _log_writer_failure is None:
            _log_writer_failure = failure
        _log_writer_state.notify_all()


def _require_log_writer_alive() -> None:
    writer = _log_writer_thread
    if _log_writer_failure is None and writer is not None and writer.is_alive():
        return
    raise RuntimeError(LOG_WRITER_TERMINATED_ERROR) from _log_writer_failure


def _start_log_writer() -> None:
    global _log_writer_thread
    with _log_writer_lock:
        if _log_writer_thread is not None:
            return
        thread = threading.Thread(target=_log_writer_loop, name="orket-log-writer", daemon=True)
        with _log_writer_state:
            _log_writer_thread = thread
        try:
            thread.start()
        except RuntimeError as exc:  # preserve process interrupts while recording thread-start failure
            _record_log_writer_failure(exc)
            _require_log_writer_alive()


def _log_writer_loop() -> None:
    try:
        while True:
            item = _log_write_queue.get()
            with _log_writer_state:
                _log_writer_state.notify_all()  # a full queue now has one available slot
            frontier = item if isinstance(item, _LogWriteFrontier) else None
            try:
                if frontier is None:
                    path, line = item
                    _append_line_sync(path, line)
            except OSError:
                pass
            finally:
                _log_write_queue.task_done()
                if frontier is not None:
                    with _log_writer_state:
                        frontier.settled = True
                        _log_writer_state.notify_all()
    except BaseException as exc:  # daemon supervisor boundary must not strand a frontier waiter
        _record_log_writer_failure(exc)
        raise


def settle_log_write_frontier() -> None:
    """Block natively until prior accepted optional appends have settled."""
    if _running_on_event_loop():
        raise RuntimeError("E_LOG_WRITE_FRONTIER_REQUIRES_NATIVE_CONTEXT: settlement blocks the calling thread")
    _start_log_writer()
    frontier = _LogWriteFrontier()
    with _log_writer_state:
        while True:
            _require_log_writer_alive()
            try:
                _log_write_queue.put_nowait(frontier)
            except queue.Full:
                _log_writer_state.wait()
            else:
                break
        while not frontier.settled:
            _require_log_writer_alive()
            _log_writer_state.wait()


def dropped_log_entry_count() -> int:
    with _dropped_log_entries_lock:
        return _dropped_log_entries


def _record_dropped_log_entry(path: Path) -> None:
    global _dropped_log_entries
    with _dropped_log_entries_lock:
        _dropped_log_entries += 1
        dropped = _dropped_log_entries
    if dropped == 1 or dropped % 1000 == 0:
        _logger.warning(
            "log_write_queue_full",
            extra={
                "orket_record": {
                    "event": "log_write_queue_full",
                    "data": {
                        "dropped_log_entries": dropped,
                        "queue_max": _log_write_queue.maxsize,
                        "path": str(path),
                    },
                }
            },
        )


def _append_line_sync(path: Path, line: str) -> None:
    _ensure_log_parent(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def _ensure_log_parent(path: Path) -> None:
    directory = path.parent.resolve()
    with _prepared_log_dirs_lock:
        if directory in _prepared_log_dirs:
            return
        directory.mkdir(parents=True, exist_ok=True)
        _prepared_log_dirs.add(directory)


def _running_on_event_loop() -> bool:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


def _append_json_record(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(payload, ensure_ascii=False, default=str) + "\n"
    if _running_on_event_loop():
        _start_log_writer()
        try:
            _log_write_queue.put_nowait((path, line))
        except queue.Full:
            _record_dropped_log_entry(path)
        return
    _append_line_sync(path, line)


def _resolve_level_name(level: Any) -> str:
    token = str(level or "").strip().lower()
    if token in _LOG_LEVELS:
        return "warning" if token == "warn" else token
    return "info"


def _emit_stdlib_record(level_name: str, event: str, record: dict[str, Any]) -> None:
    _logger.log(_LOG_LEVELS[level_name], str(event or "").strip(), extra={"orket_record": record})


def setup_logging(workspace: Path) -> Path:
    """Ensures workspace log directory exists and returns the target log file."""
    path = workspace / "orket.log"
    _ensure_log_parent(path)
    return path


class EventSubscription:
    """Registration state belongs to the process publication owner's condition."""

    def __init__(self, callback: Callable[..., None], *, handoff: bool = False) -> None:
        self.callback = callback
        self.handoff = handoff
        self.state = "open"
        self.pending = 0


class EventDelivery:
    def __init__(self, subscription: EventSubscription) -> None:
        self.subscription = subscription
        self.acknowledged = False
        self.transferred = False

    def acknowledge(self) -> None:
        with _log_writer_state:
            if not self.acknowledged:
                self.acknowledged = True
                self.subscription.pending -= 1
                _log_writer_state.notify_all()

    def invoke(self, record: dict[str, Any]) -> None:
        completed = False
        try:
            if self.subscription.handoff:
                self.subscription.callback(record, self.acknowledge)
            else:
                self.subscription.callback(record)
            completed = True
        finally:
            self.transferred = completed and self.subscription.handoff
            if not self.transferred:
                self.acknowledge()

    def release_untransferred(self) -> None:
        if not self.transferred:
            self.acknowledge()


_subscribers: list[EventSubscription] = []


def capture_event_deliveries() -> list[EventDelivery]:
    with _log_writer_state:
        deliveries = [EventDelivery(item) for item in _subscribers if item.state == "open"]
        for delivery in deliveries:
            delivery.subscription.pending += 1
        return deliveries


def subscribe_to_event_handoffs(callback: Callable[[dict[str, Any], Callable[[], None]], None]) -> EventSubscription:
    """Register a sink that acknowledges its own later queue-handoff attempt."""
    subscription = EventSubscription(callback, handoff=True)
    with _log_writer_state:
        _subscribers.append(subscription)
    return subscription


def begin_event_subscription_drain(subscription: EventSubscription) -> None:
    with _log_writer_state:
        if subscription.state == "open":
            subscription.state = "draining"


def settle_event_subscription(subscription: EventSubscription) -> None:
    """Wait natively for this registration only; never stop the shared writer."""
    if _running_on_event_loop():
        raise RuntimeError("E_LOG_SUBSCRIPTION_DRAIN_REQUIRES_NATIVE_CONTEXT")
    begin_event_subscription_drain(subscription)
    with _log_writer_state:
        while subscription.pending:
            _log_writer_state.wait()
        if subscription in _subscribers:
            _subscribers.remove(subscription)
        subscription.state = "closed"


def subscribe_to_events(callback: Callable[[dict[str, Any]], None]) -> None:
    with _log_writer_state:
        if not any(item.callback == callback and not item.handoff for item in _subscribers):
            _subscribers.append(EventSubscription(callback))


def unsubscribe_from_events(callback: Callable[[dict[str, Any]], None]) -> None:
    with _log_writer_state:
        for item in _subscribers:
            if item.callback == callback and not item.handoff:
                item.state = "closed"
                _subscribers.remove(item)
                break


def event_subscriber_count() -> int:
    with _log_writer_state:
        return len(_subscribers)
