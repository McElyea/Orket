"""Native child lifetime remains owned across spawn, registration and teardown."""
import asyncio

import pytest

import orket.application.services.governed_agent_process_owner as owner_module
from orket.adapters.execution.process_lifecycle import terminate_process_tree
from orket.extensions.governed_agent_invoker import GovernedAgentSubprocessInvoker
from orket_extension_sdk.agent_fixtures import agent_cancellation
from tests.helpers.governed_agent_clock import elapsed_agent_clock as elapsed_agent_clock
from tests.runtime.governed_agent_test_support import UnexpectedBroker, agent_request, binding_for

pytestmark = pytest.mark.integration


def make_invoker(root):
    (root / "waiting_agent.py").write_text(
        "class WaitingAgent:\n"
        "    async def run(self, context):\n"
        "        await context.cancellation.wait()\n", encoding="utf-8",
    )
    return GovernedAgentSubprocessInvoker(
        extension_root=root, entrypoint="waiting_agent:WaitingAgent",
        allowed_stdlib_modules=(), broker=UnexpectedBroker(), handshake_timeout_seconds=2,
    )


@pytest.mark.asyncio
async def test_operator_cancel_during_spawn_keeps_cleanup_uncertain(tmp_path, monkeypatch, elapsed_agent_clock):
    """Layer: integration. Pending native launch cannot be reported already stopped."""
    invoker = make_invoker(tmp_path)
    spawned, release, children = asyncio.Event(), asyncio.Event(), []
    start = invoker._start_child

    async def held_start():
        process = await start()
        children.append(process)
        spawned.set()
        await release.wait()
        return process

    monkeypatch.setattr(invoker, "_start_child", held_start)
    request = agent_request()
    binding = binding_for(request)
    task = asyncio.create_task(invoker.invoke_once(binding=binding, request_payload=request))
    try:
        await asyncio.wait_for(spawned.wait(), 5)
        stopped = await invoker.cancel_and_reap(binding=binding, cancellation_payload={}, grace_period_seconds=0.01)
        assert stopped is False, "pending launch was incorrectly reported stopped"
        release.set()
        outcome = await asyncio.wait_for(task, 5)
        assert outcome.status == "cancelled" and outcome.child_confirmed_stopped
        assert children[0].returncode is not None
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        for child in children:
            await terminate_process_tree(child)


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["spawn", "teardown"])
async def test_repeated_cancellation_retains_native_transition(tmp_path, monkeypatch, elapsed_agent_clock, phase):
    """Layer: integration. A real process transition must settle before cancellation returns."""
    invoker = make_invoker(tmp_path)
    entered, release, spawned = asyncio.Event(), asyncio.Event(), asyncio.Event()
    children = []
    start = invoker._start_child

    async def observed_start():
        process = await start()
        children.append(process)
        spawned.set()
        if phase == "spawn":
            entered.set()
            await release.wait()
        return process

    async def held_stop(process):
        entered.set()
        await release.wait()
        await terminate_process_tree(process)

    monkeypatch.setattr(invoker, "_start_child", observed_start)
    if phase == "teardown":
        monkeypatch.setattr(owner_module, "terminate_process_tree", held_stop)
    request = agent_request()
    task = asyncio.create_task(invoker.invoke_once(binding=binding_for(request), request_payload=request))
    try:
        await asyncio.wait_for(spawned.wait(), 5)
        if phase == "teardown":
            task.cancel()
        await asyncio.wait_for(entered.wait(), 5)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done(), "caller returned before its native transition settled"
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 5)
        assert children[0].returncode is not None
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        for child in children:
            await terminate_process_tree(child)


@pytest.mark.asyncio
async def test_duplicate_pending_launch_does_not_claim_existing_child_stopped(tmp_path, monkeypatch, elapsed_agent_clock):
    """Layer: integration. A rejected duplicate cannot attest to the first caller's cleanup."""
    invoker = make_invoker(tmp_path)
    entered, release, children = asyncio.Event(), asyncio.Event(), []
    start = invoker._start_child

    async def held_start():
        process = await start()
        children.append(process)
        entered.set()
        await release.wait()
        return process

    monkeypatch.setattr(invoker, "_start_child", held_start)
    request = agent_request()
    binding = binding_for(request)
    first = asyncio.create_task(invoker.invoke_once(binding=binding, request_payload=request))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        duplicate = await invoker.invoke_once(binding=binding, request_payload=request)
        assert duplicate.normalized_reason == "E_AGENT_INVOCATION_ALREADY_ACTIVE"
        assert len(children) == 1 and children[0].returncode is None
        assert duplicate.child_confirmed_stopped is False
    finally:
        first.cancel()
        release.set()
        await asyncio.gather(first, return_exceptions=True)
        for child in children:
            await terminate_process_tree(child)


@pytest.mark.asyncio
async def test_operator_cancel_captures_payload_before_await(tmp_path, monkeypatch, elapsed_agent_clock):
    """Layer: integration. The real child reports the originally submitted cancellation reason."""
    invoker = make_invoker(tmp_path)
    (tmp_path / "waiting_agent.py").write_text(
        "class WaitingAgent:\n"
        "    async def run(self, context):\n"
        "        await context.cancellation.wait()\n"
        "        raise RuntimeError(context.cancellation.snapshot().reason)\n", encoding="utf-8",
    )
    bootstrapped = asyncio.Event()
    bootstrap = invoker._send_bootstrap

    async def observed_bootstrap(*args):
        await bootstrap(*args)
        bootstrapped.set()

    monkeypatch.setattr(invoker, "_send_bootstrap", observed_bootstrap)
    request = agent_request()
    binding = binding_for(request)
    invocation = asyncio.create_task(invoker.invoke_once(binding=binding, request_payload=request))
    payload = agent_cancellation(requested=True)
    payload["reason"] = "original cancellation"
    try:
        await asyncio.wait_for(bootstrapped.wait(), 5)
        cancellation = asyncio.create_task(invoker.cancel_and_reap(
            binding=binding, cancellation_payload=payload, grace_period_seconds=2))
        await asyncio.sleep(0)
        payload["reason"] = "mutated cancellation"
        assert await asyncio.wait_for(cancellation, 5)
        assert (await asyncio.wait_for(invocation, 5)).status == "cancelled"
        assert "original cancellation" in invoker.last_diagnostic_tail
        assert "mutated cancellation" not in invoker.last_diagnostic_tail
    finally:
        if not invocation.done():
            invocation.cancel()
        await asyncio.gather(invocation, return_exceptions=True)


@pytest.mark.asyncio
async def test_failed_cleanup_is_not_hidden_by_cancellation(tmp_path, monkeypatch, elapsed_agent_clock):
    """Layer: integration. Failed native teardown remains an error with a retained owner."""
    invoker = make_invoker(tmp_path)
    spawned, children = asyncio.Event(), []
    start = invoker._start_child

    async def observed_start():
        process = await start()
        children.append(process)
        spawned.set()
        return process

    async def refused_stop(_process):
        raise OSError("fixture native cleanup refused")

    monkeypatch.setattr(invoker, "_start_child", observed_start)
    monkeypatch.setattr(owner_module, "terminate_process_tree", refused_stop)
    request = agent_request()
    binding = binding_for(request)
    task = asyncio.create_task(invoker.invoke_once(binding=binding, request_payload=request))
    try:
        await asyncio.wait_for(spawned.wait(), 5)
        task.cancel()
        with pytest.raises(OSError, match="fixture native cleanup refused"):
            await asyncio.wait_for(task, 5)
        owner = invoker._active[binding.invocation_id]
        assert not owner.finished.is_set() and children[0].returncode is None
    finally:
        monkeypatch.setattr(owner_module, "terminate_process_tree", terminate_process_tree)
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        owner = invoker._active.get(binding.invocation_id)
        if owner is not None:
            await invoker._finish_active(owner)


@pytest.mark.asyncio
async def test_concurrent_children_keep_independent_cancellation_owners(tmp_path, monkeypatch, elapsed_agent_clock):
    """Layer: integration. Cancelling one real child leaves the other invocation alive."""
    invoker = make_invoker(tmp_path)
    bootstrapped = asyncio.Queue()
    bootstrap = invoker._send_bootstrap

    async def observed_bootstrap(active, request):
        await bootstrap(active, request)
        bootstrapped.put_nowait(active.binding.invocation_id)

    monkeypatch.setattr(invoker, "_send_bootstrap", observed_bootstrap)
    first, second = agent_request(), agent_request()
    second["identity"]["invocation_id"] = "invocation-2"
    bindings = [binding_for(request) for request in (first, second)]
    tasks = [asyncio.create_task(invoker.invoke_once(binding=binding, request_payload=request))
             for binding, request in zip(bindings, (first, second), strict=True)]
    try:
        observed = {await asyncio.wait_for(bootstrapped.get(), 5) for _ in tasks}
        assert observed == {binding.invocation_id for binding in bindings}
        assert await invoker.cancel_and_reap(binding=bindings[0], cancellation_payload=agent_cancellation(requested=True),
                                             grace_period_seconds=0.1)
        assert (await asyncio.wait_for(tasks[0], 5)).status == "cancelled"
        assert not tasks[1].done()
        assert invoker._active[bindings[1].invocation_id].process.returncode is None
        assert await invoker.cancel_and_reap(binding=bindings[1], cancellation_payload=agent_cancellation(requested=True),
                                             grace_period_seconds=0.1)
        assert (await asyncio.wait_for(tasks[1], 5)).status == "cancelled"
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.asyncio
async def test_foreign_loop_cannot_cancel_the_native_owner(tmp_path, monkeypatch, elapsed_agent_clock):
    """Layer: integration. A foreign event loop is refused while the real child stays owned."""
    invoker = make_invoker(tmp_path)
    spawned, children = asyncio.Event(), []
    start = invoker._start_child

    async def observed_start():
        process = await start()
        children.append(process)
        spawned.set()
        return process

    monkeypatch.setattr(invoker, "_start_child", observed_start)
    request = agent_request()
    binding = binding_for(request)
    task = asyncio.create_task(invoker.invoke_once(binding=binding, request_payload=request))
    try:
        await asyncio.wait_for(spawned.wait(), 5)
        with pytest.raises(ValueError, match="E_AGENT_INVOCATION_OWNER:event_loop_mismatch"):
            await asyncio.to_thread(lambda: asyncio.run(invoker.cancel_and_reap(
                binding=binding, cancellation_payload=agent_cancellation(requested=True), grace_period_seconds=0.1)))
        assert children[0].returncode is None and not task.done()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert children[0].returncode is not None
