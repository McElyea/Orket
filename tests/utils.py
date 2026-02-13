from __future__ import annotations

import random
import threading
import time
from typing import Callable

from fastapi.testclient import TestClient

from orket.core.domain.coordinator_card import Card
from orket.interfaces.coordinator_api import app, store


class DelayedTestClient:
    def __init__(self, client: TestClient, delay_fn: Callable[[], None] | None = None) -> None:
        self._client = client
        self._delay_fn = delay_fn

    def get(self, url: str):
        if self._delay_fn is not None:
            self._delay_fn()
        return self._client.get(url)

    def post(self, url: str, json: dict):
        if self._delay_fn is not None:
            self._delay_fn()
        return self._client.post(url, json=json)


class PausableMonotonic:
    def __init__(self) -> None:
        self._base_real = time.monotonic()
        self._paused_total = 0.0
        self._paused = False
        self._paused_real_at = 0.0
        self._lock = threading.Lock()

    def __call__(self) -> float:
        with self._lock:
            if self._paused:
                return self._paused_real_at - self._base_real - self._paused_total
            return time.monotonic() - self._base_real - self._paused_total

    def pause(self) -> None:
        with self._lock:
            if self._paused:
                return
            self._paused_real_at = time.monotonic()
            self._paused = True

    def resume(self) -> None:
        with self._lock:
            if not self._paused:
                return
            now_real = time.monotonic()
            self._paused_total += now_real - self._paused_real_at
            self._paused = False


def make_delay(seed: int, minimum: float = 0.001, maximum: float = 0.005) -> Callable[[], None]:
    rng = random.Random(seed)

    def _delay() -> None:
        time.sleep(rng.uniform(minimum, maximum))

    return _delay


def make_client(seed: int = 7) -> DelayedTestClient:
    base_client = TestClient(app)
    return DelayedTestClient(base_client, delay_fn=make_delay(seed))


def reset_store_with_cards(cards: list[Card]) -> None:
    store.reset(cards)


def wait_until(predicate: Callable[[], bool], timeout: float = 2.0, interval: float = 0.01) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


