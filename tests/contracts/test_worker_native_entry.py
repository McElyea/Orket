"""Layer: contract. Refuse async blocking before controlled collaborator effects."""
from types import SimpleNamespace

import pytest

from orket.adapters.execution.worker_client import Worker, make_random_delay

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


@pytest.mark.parametrize("operation", ["poll", "claim", "renew", "complete", "fail", "once", "claimed", "delay"])
async def test_worker_native_entry_refuses_running_loop(operation):
    effects = []
    response = SimpleNamespace(status_code=200, json=lambda: [])
    client = SimpleNamespace(get=lambda *_args: effects.append("get") or response,
                             post=lambda *_args, **_kwargs: effects.append("post") or response)
    worker = Worker(node_id="fixture", base_url="http://unused", client=client,
                    sleep_fn=lambda _seconds: effects.append("sleep"),
                    network_delay_fn=lambda: effects.append("network-delay"))
    invoke = {
        "poll": worker.poll_open_cards,
        "claim": lambda: worker.claim("card"),
        "renew": lambda: worker.renew("card"),
        "complete": lambda: worker.complete("card"),
        "fail": lambda: worker.fail("card"),
        "once": worker.run_once,
        "claimed": lambda: worker.run_claimed_work("card", work_duration=0, completion_result={}),
        "delay": make_random_delay(7, minimum=0, maximum=0),
    }[operation]
    with pytest.raises(RuntimeError, match="E_WORKER_REQUIRES_ASYNC_OWNER"):
        invoke()
    assert effects == []
