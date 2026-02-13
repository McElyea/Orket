from __future__ import annotations

import random
import threading
import time
from typing import Any, Callable, Protocol


class ResponseLike(Protocol):
    status_code: int
    text: str

    def json(self) -> dict[str, Any] | list[dict[str, Any]]:
        ...


class ClientLike(Protocol):
    def get(self, url: str) -> ResponseLike:
        ...

    def post(self, url: str, json: dict[str, Any]) -> ResponseLike:
        ...


class Worker:
    def __init__(
        self,
        *,
        node_id: str,
        base_url: str,
        client: ClientLike,
        lease_duration: float = 1.0,
        poll_interval: float = 0.05,
        renew_interval: float | None = None,
        monotonic_fn: Callable[[], float] = time.monotonic,
        sleep_fn: Callable[[float], None] = time.sleep,
        network_delay_fn: Callable[[], None] | None = None,
    ) -> None:
        self.node_id = node_id
        self.base_url = base_url.rstrip("/")
        self.client = client
        self.lease_duration = lease_duration
        self.poll_interval = poll_interval
        self.renew_interval = renew_interval if renew_interval is not None else (lease_duration / 3.0)
        self.monotonic_fn = monotonic_fn
        self.sleep_fn = sleep_fn
        self.network_delay_fn = network_delay_fn

    def _delay(self) -> None:
        if self.network_delay_fn is not None:
            self.network_delay_fn()

    def _get(self, path: str) -> ResponseLike:
        self._delay()
        return self.client.get(f"{self.base_url}{path}")

    def _post(self, path: str, payload: dict[str, Any]) -> ResponseLike:
        self._delay()
        return self.client.post(f"{self.base_url}{path}", json=payload)

    def poll_open_cards(self) -> list[dict[str, Any]]:
        response = self._get("/cards?state=open")
        if response.status_code != 200:
            return []
        payload = response.json()
        if isinstance(payload, list):
            return payload
        return []

    def claim(self, card_id: str) -> ResponseLike:
        return self._post(
            f"/cards/{card_id}/claim",
            {"node_id": self.node_id, "lease_duration": self.lease_duration},
        )

    def renew(self, card_id: str) -> ResponseLike:
        return self._post(
            f"/cards/{card_id}/renew",
            {"node_id": self.node_id, "lease_duration": self.lease_duration},
        )

    def complete(self, card_id: str, result: dict[str, Any] | None = None) -> ResponseLike:
        return self._post(
            f"/cards/{card_id}/complete",
            {"node_id": self.node_id, "result": result or {"worker": self.node_id, "status": "done"}},
        )

    def fail(self, card_id: str, result: dict[str, Any] | None = None) -> ResponseLike:
        return self._post(
            f"/cards/{card_id}/fail",
            {"node_id": self.node_id, "result": result or {"worker": self.node_id, "status": "failed"}},
        )

    def _renew_loop(self, card_id: str, stop_event: threading.Event) -> None:
        next_renew = self.monotonic_fn() + self.renew_interval
        while not stop_event.is_set():
            now = self.monotonic_fn()
            if now >= next_renew:
                renew_response = self.renew(card_id)
                if renew_response.status_code != 200:
                    return
                next_renew = now + self.renew_interval
            self.sleep_fn(0.005)

    def run_claimed_work(self, card_id: str, *, work_duration: float, completion_result: dict[str, Any]) -> ResponseLike:
        stop_event = threading.Event()
        renew_thread = threading.Thread(target=self._renew_loop, args=(card_id, stop_event), daemon=True)
        renew_thread.start()
        deadline = self.monotonic_fn() + work_duration
        while self.monotonic_fn() < deadline:
            self.sleep_fn(0.005)
        stop_event.set()
        renew_thread.join(timeout=2.0)
        return self.complete(card_id, completion_result)

    def run_once(self, *, work_duration: float = 0.1) -> bool:
        cards = self.poll_open_cards()
        if not cards:
            self.sleep_fn(self.poll_interval)
            return False
        for card in cards:
            card_id = str(card["id"])
            claim_response = self.claim(card_id)
            if claim_response.status_code == 200:
                self.run_claimed_work(
                    card_id,
                    work_duration=work_duration,
                    completion_result={"worker": self.node_id, "state": "done"},
                )
                return True
        self.sleep_fn(self.poll_interval)
        return False


def make_random_delay(seed: int, minimum: float = 0.0, maximum: float = 0.02) -> Callable[[], None]:
    rng = random.Random(seed)

    def _delay() -> None:
        time.sleep(rng.uniform(minimum, maximum))

    return _delay
