from __future__ import annotations

import os
import sys
import threading
import time

from orket.adapters.execution.worker_client import Worker
from orket.core.domain.coordinator_card import Card
sys.path.append(os.path.dirname(__file__))
from utils import PausableMonotonic, make_client, reset_store_with_cards


def test_lease_expiration_takeover_with_paused_worker_monotonic() -> None:
    reset_store_with_cards(
        [
            Card(
                id="lease-card",
                payload={"job": "lease-expiration"},
                state="OPEN",
                claimed_by=None,
                lease_expires_at=None,
                result=None,
                attempts=0,
                hedged_execution=False,
            )
        ]
    )

    client = make_client(seed=101)
    paused_clock = PausableMonotonic()
    worker_a = Worker(
        node_id="worker-a",
        base_url="",
        client=client,
        lease_duration=0.25,
        renew_interval=0.10,
        monotonic_fn=paused_clock,
    )

    worker_b = Worker(
        node_id="worker-b",
        base_url="",
        client=client,
        lease_duration=0.25,
        renew_interval=0.10,
    )

    claim_a = worker_a.claim("lease-card")
    assert claim_a.status_code == 200

    completion_holder: dict[str, int] = {}

    def _worker_a_job() -> None:
        response = worker_a.run_claimed_work(
            "lease-card",
            work_duration=0.7,
            completion_result={"worker": "worker-a"},
        )
        completion_holder["status"] = response.status_code

    thread = threading.Thread(target=_worker_a_job, daemon=True)
    thread.start()
    time.sleep(0.03)
    paused_clock.pause()

    time.sleep(0.35)
    claim_b = worker_b.claim("lease-card")
    assert claim_b.status_code == 200
    assert claim_b.json()["claimed_by"] == "worker-b"

    paused_clock.resume()
    thread.join(timeout=2.0)
    assert "status" in completion_holder
    assert completion_holder["status"] in (403, 409, 200)

