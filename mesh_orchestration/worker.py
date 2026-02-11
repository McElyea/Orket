from __future__ import annotations

import threading
import time
from typing import Any

import httpx


def _renew_loop(
    *,
    base_url: str,
    card_id: str,
    node_id: str,
    lease_seconds: int,
    stop_event: threading.Event,
) -> None:
    while not stop_event.is_set():
        time.sleep(max(0.5, lease_seconds / 2))
        if stop_event.is_set():
            return
        try:
            response = httpx.post(
                f"{base_url}/cards/{card_id}/renew",
                json={"node_id": node_id, "lease_seconds": lease_seconds},
                timeout=2.0,
            )
            if response.status_code != 200:
                print(f"[{node_id}] renew failed {response.status_code}: {response.text}")
                return
            print(f"[{node_id}] lease renewed")
        except Exception as exc:  # noqa: BLE001
            print(f"[{node_id}] renew exception: {exc}")
            return


def run_worker(
    *,
    node_id: str,
    base_url: str = "http://127.0.0.1:8000",
    lease_seconds: int = 3,
    poll_interval: float = 0.75,
    work_seconds: int = 6,
    crash_after_claim: bool = False,
    max_runtime_seconds: int = 20,
) -> None:
    print(f"[{node_id}] started")
    deadline = time.time() + max_runtime_seconds
    while True:
        if time.time() > deadline:
            print(f"[{node_id}] exiting after max runtime")
            return

        try:
            open_response = httpx.get(f"{base_url}/cards?state=open", timeout=2.0)
            open_response.raise_for_status()
            open_cards = open_response.json()
        except Exception as exc:  # noqa: BLE001
            print(f"[{node_id}] polling error: {exc}")
            time.sleep(poll_interval)
            continue

        if not open_cards:
            time.sleep(poll_interval)
            continue

        card_id = open_cards[0]["id"]
        claim_response = httpx.post(
            f"{base_url}/cards/{card_id}/claim",
            json={"node_id": node_id, "lease_seconds": lease_seconds},
            timeout=2.0,
        )
        if claim_response.status_code != 200:
            time.sleep(poll_interval)
            continue

        print(f"[{node_id}] claimed {card_id}")
        if crash_after_claim:
            print(f"[{node_id}] simulating crash: lease will expire without renew")
            time.sleep(lease_seconds + 1)
            print(f"[{node_id}] crashed")
            return

        stop_event = threading.Event()
        renew_thread = threading.Thread(
            target=_renew_loop,
            kwargs={
                "base_url": base_url,
                "card_id": card_id,
                "node_id": node_id,
                "lease_seconds": lease_seconds,
                "stop_event": stop_event,
            },
            daemon=True,
        )
        renew_thread.start()

        success = True
        result: Any = None
        try:
            print(f"[{node_id}] handling {card_id} for {work_seconds}s")
            time.sleep(work_seconds)
            result = {"handled_by": node_id, "status": "ok"}
        except Exception as exc:  # noqa: BLE001
            success = False
            result = {"handled_by": node_id, "status": "error", "message": str(exc)}
        finally:
            stop_event.set()
            renew_thread.join(timeout=2.0)

        endpoint = "complete" if success else "fail"
        payload = {"node_id": node_id, "result": result}
        finalize_response = httpx.post(
            f"{base_url}/cards/{card_id}/{endpoint}",
            json=payload,
            timeout=2.0,
        )

        if finalize_response.status_code in (200, 409):
            print(f"[{node_id}] submitted {endpoint} for {card_id}")
            return

        print(
            f"[{node_id}] finalize failed {finalize_response.status_code}: {finalize_response.text}"
        )
        return
