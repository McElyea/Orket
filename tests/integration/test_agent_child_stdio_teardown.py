"""Native child failure must leave stdio without an interpreter-shutdown abort."""
import pytest

from orket.extensions.governed_agent_invoker import GovernedAgentSubprocessInvoker
from tests.helpers.governed_agent_clock import elapsed_agent_clock as elapsed_agent_clock
from tests.runtime.governed_agent_test_support import UnexpectedBroker, agent_request, binding_for

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_child_crash_exits_normally_with_parent_input_open(tmp_path, monkeypatch, elapsed_agent_clock):
    """Layer: integration. Real framed bootstrap, crashing workload and reaped process."""
    (tmp_path / "crash_agent.py").write_text(
        "class CrashAgent:\n"
        "    async def run(self, context):\n"
        "        raise RuntimeError('fixture child crash')\n", encoding="utf-8",
    )
    invoker = GovernedAgentSubprocessInvoker(
        extension_root=tmp_path, entrypoint="crash_agent:CrashAgent",
        allowed_stdlib_modules=(), broker=UnexpectedBroker(), handshake_timeout_seconds=2,
    )
    children = []
    start_child = invoker._start_child

    async def observe_child():
        process = await start_child()
        children.append(process)
        return process

    monkeypatch.setattr(invoker, "_start_child", observe_child)
    request = agent_request()
    outcome = await invoker.invoke_once(binding=binding_for(request), request_payload=request)
    assert outcome.normalized_reason == "E_AGENT_CHILD_DISCONNECTED", invoker.last_diagnostic_tail
    assert outcome.child_confirmed_stopped and len(children) == 1
    assert children[0].returncode == 1, invoker.last_diagnostic_tail
    assert "RuntimeError: fixture child crash" in invoker.last_diagnostic_tail
    assert "Fatal Python error" not in invoker.last_diagnostic_tail
