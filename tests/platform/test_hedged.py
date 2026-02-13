from __future__ import annotations

import os
import sys
import threading
import time

from orket.adapters.execution.worker_client import Worker
from orket.core.domain.coordinator_card import Card
sys.path.append(os.path.dirname(__file__))
from utils import make_client, reset_store_with_cards


def test_hedged_execution_first_completion_wins() -> None:
    reset_store_with_cards(
        [
            Card(
                id="hedged-card",
                payload={"job": "hedged"},
                state="OPEN",
                claimed_by=None,
                lease_expires_at=None,
                result=None,
                attempts=0,
                hedged_execution=True,
            )
        ]
    )

    client = make_client(seed=202)
    worker_a = Worker(
        node_id="worker-a",
        base_url="",
        client=client,
        lease_duration=0.60,
        renew_interval=0.35,
    )
    worker_b = Worker(
        node_id="worker-b",
        base_url="",
        client=client,
        lease_duration=0.60,
        renew_interval=0.10,
    )

    claim_a = worker_a.claim("hedged-card")
    assert claim_a.status_code == 200

    time.sleep(0.34)
    claim_b = worker_b.claim("hedged-card")
    assert claim_b.status_code == 200

    results: dict[str, int] = {}

    def _complete_b_first() -> None:
        resp = worker_b.run_claimed_work(
            "hedged-card",
            work_duration=0.05,
            completion_result={"worker": "worker-b", "winner": True},
        )
        results["b"] = resp.status_code

    def _complete_a_later() -> None:
        resp = worker_a.run_claimed_work(
            "hedged-card",
            work_duration=0.12,
            completion_result={"worker": "worker-a", "winner": False},
        )
        results["a"] = resp.status_code

    thread_b = threading.Thread(target=_complete_b_first, daemon=True)
    thread_a = threading.Thread(target=_complete_a_later, daemon=True)
    thread_b.start()
    time.sleep(0.01)
    thread_a.start()
    thread_b.join(timeout=2.0)
    thread_a.join(timeout=2.0)

    assert results["b"] == 200
    assert results["a"] == 200

    complete_again_a = worker_a.complete("hedged-card", {"worker": "worker-a", "late": True})
    assert complete_again_a.status_code == 200
    body = complete_again_a.json()
    assert body["state"] == "DONE"
    assert body["result"] == {"worker": "worker-b", "winner": True}

