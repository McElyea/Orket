from __future__ import annotations

import asyncio

import pytest

from orket.application.services.gitea_state_worker import GiteaStateWorker


class _FakeAdapter:
    def __init__(self):
        self.cards = []
        self.acquire_result = None
        self.calls = []
        self.renew_count = 0
        self.renew_results = []
        self.transition_error = None

    async def fetch_ready_cards(self, *, limit: int = 1):
        self.calls.append(("fetch_ready_cards", limit))
        return list(self.cards)

    async def acquire_lease(self, card_id: str, *, owner_id: str, lease_seconds: int):
        self.calls.append(("acquire_lease", card_id, owner_id, lease_seconds))
        return self.acquire_result

    async def transition_state(self, card_id: str, *, from_state: str, to_state: str, reason: str | None = None):
        self.calls.append(("transition_state", card_id, from_state, to_state, reason))
        if self.transition_error is not None:
            raise self.transition_error

    async def renew_lease(self, card_id: str, *, owner_id: str, lease_seconds: int, expected_lease_epoch=None):
        self.renew_count += 1
        self.calls.append(("renew_lease", card_id, owner_id, lease_seconds, expected_lease_epoch))
        if self.renew_results:
            return self.renew_results.pop(0)
        return {"ok": True}

    async def release_or_fail(self, card_id: str, *, final_state: str, error: str | None = None):
        self.calls.append(("release_or_fail", card_id, final_state, error))


@pytest.mark.asyncio
async def test_run_once_returns_false_when_no_candidates():
    adapter = _FakeAdapter()
    worker = GiteaStateWorker(adapter=adapter, worker_id="worker-a")

    async def _work(_card):
        return {"ok": True}

    consumed = await worker.run_once(work_fn=_work)
    assert consumed is False
    assert adapter.calls == [("fetch_ready_cards", 5)]


@pytest.mark.asyncio
async def test_run_once_success_flow_transitions_and_releases():
    adapter = _FakeAdapter()
    adapter.cards = [{"issue_number": 7, "state": "ready"}]
    adapter.acquire_result = {"card_id": "ISSUE-7", "lease_epoch": 1}
    worker = GiteaStateWorker(adapter=adapter, worker_id="worker-a")

    async def _work(card):
        assert card["issue_number"] == 7
        return {"ok": True}

    consumed = await worker.run_once(work_fn=_work)
    assert consumed is True
    assert ("transition_state", "7", "ready", "in_progress", "worker_claimed:worker-a") in adapter.calls
    assert ("release_or_fail", "7", "code_review", None) in adapter.calls


@pytest.mark.asyncio
async def test_run_once_failure_flow_releases_blocked_with_error():
    adapter = _FakeAdapter()
    adapter.cards = [{"issue_number": 9, "state": "ready"}]
    adapter.acquire_result = {"card_id": "ISSUE-9", "lease_epoch": 2}
    worker = GiteaStateWorker(adapter=adapter, worker_id="worker-a")

    async def _work(_card):
        raise RuntimeError("boom")

    consumed = await worker.run_once(work_fn=_work)
    assert consumed is True
    matching = [item for item in adapter.calls if item[0] == "release_or_fail"]
    assert matching
    assert matching[-1][1] == "9"
    assert matching[-1][2] == "blocked"
    assert "boom" in str(matching[-1][3])


@pytest.mark.asyncio
async def test_run_once_claim_transition_failure_without_control_plane_still_raises():
    adapter = _FakeAdapter()
    adapter.cards = [{"issue_number": 10, "state": "ready"}]
    adapter.acquire_result = {"card_id": "ISSUE-10", "lease_epoch": 1}
    adapter.transition_error = ValueError("Stale transition rejected for 10")
    worker = GiteaStateWorker(adapter=adapter, worker_id="worker-a")

    async def _work(_card):
        return {"ok": True}

    with pytest.raises(ValueError, match="Stale transition rejected"):
        await worker.run_once(work_fn=_work)


@pytest.mark.asyncio
async def test_renew_loop_heartbeats_while_work_in_progress():
    adapter = _FakeAdapter()
    adapter.cards = [{"issue_number": 12, "state": "ready"}]
    adapter.acquire_result = {"card_id": "ISSUE-12", "lease_epoch": 3}
    worker = GiteaStateWorker(
        adapter=adapter,
        worker_id="worker-a",
        lease_seconds=1,
        renew_interval_seconds=0.1,
    )

    async def _work(_card):
        await asyncio.sleep(0.25)
        return {"ok": True}

    consumed = await worker.run_once(work_fn=_work)
    assert consumed is True
    assert adapter.renew_count >= 1


@pytest.mark.asyncio
async def test_run_once_lease_expiry_signal_transitions_to_failure():
    adapter = _FakeAdapter()
    adapter.cards = [{"issue_number": 15, "state": "ready"}]
    adapter.acquire_result = {"card_id": "ISSUE-15", "lease_epoch": 7}
    adapter.renew_results = [{"ok": False, "error_code": "E_LEASE_EXPIRED"}]
    worker = GiteaStateWorker(
        adapter=adapter,
        worker_id="worker-a",
        lease_seconds=1,
        renew_interval_seconds=0.05,
    )

    async def _work(_card):
        await asyncio.sleep(0.15)
        return {"ok": True}

    consumed = await worker.run_once(work_fn=_work)
    assert consumed is True
    releases = [row for row in adapter.calls if row[0] == "release_or_fail"]
    assert releases
    assert releases[-1][2] == "blocked"
    assert "E_LEASE_EXPIRED" in str(releases[-1][3])


@pytest.mark.asyncio
async def test_run_once_lease_epoch_mismatch_transitions_to_failure():
    adapter = _FakeAdapter()
    adapter.cards = [{"issue_number": 16, "state": "ready"}]
    adapter.acquire_result = {"card_id": "ISSUE-16", "lease_epoch": 10}
    adapter.renew_results = [{"ok": True, "lease_epoch": 11}]
    worker = GiteaStateWorker(
        adapter=adapter,
        worker_id="worker-a",
        lease_seconds=1,
        renew_interval_seconds=0.05,
    )

    async def _work(_card):
        await asyncio.sleep(0.15)
        return {"ok": True}

    consumed = await worker.run_once(work_fn=_work)
    assert consumed is True
    releases = [row for row in adapter.calls if row[0] == "release_or_fail"]
    assert releases
    assert releases[-1][2] == "blocked"
    assert "E_LEASE_EXPIRED" in str(releases[-1][3])


def test_lease_epoch_supports_real_adapter_nested_lease_shape() -> None:
    lease = {
        "card_id": "ISSUE-20",
        "issue_number": 20,
        "lease": {
            "owner_id": "worker-a",
            "acquired_at": "2026-03-24T01:00:00+00:00",
            "expires_at": "2026-03-24T01:00:30+00:00",
            "epoch": 4,
        },
        "version": 9,
    }

    assert GiteaStateWorker._lease_epoch(lease) == 4


def test_is_lease_expired_detects_nested_epoch_mismatch() -> None:
    renewed = {
        "card_id": "ISSUE-21",
        "issue_number": 21,
        "lease": {
            "owner_id": "worker-a",
            "acquired_at": "2026-03-24T01:00:00+00:00",
            "expires_at": "2026-03-24T01:01:00+00:00",
            "epoch": 5,
        },
        "version": 10,
    }

    assert GiteaStateWorker._is_lease_expired(renewed, expected_epoch=4) is True
