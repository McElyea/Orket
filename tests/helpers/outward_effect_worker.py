"""Real API worker paused after a named durable effect boundary for parent-process termination."""

from __future__ import annotations

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import aiofiles

from tests.helpers.outward_authorization import FixedInputs, approve, outward_api
from tests.helpers.outward_model import FakeOutwardModelClient


class CountedModelClient(FakeOutwardModelClient):
    """Explicit provider fixture with independently retained invocation count."""

    def __init__(self, root: Path, calls: list[dict]) -> None:
        super().__init__()
        self.root, self.calls = root, calls

    async def complete(self, messages, runtime_context=None):
        turn = runtime_context["turn_number"]
        call = self.calls[turn - 1]
        self.tool, self.args = call["tool"], call["args"]
        async with aiofiles.open(self.root / "model_invocations.txt", "a", encoding="utf-8") as handle:
            await handle.write(f"{turn}\n")
        return await super().complete(messages, runtime_context)


async def run(root: Path, proposal_id: str, checkpoint: str, recovery_request: dict | None = None) -> None:
    async with outward_api(root, FixedInputs()) as (client, context):
        execution = context.outward_run_execution_service
        effects, models = execution.effects, execution.models
        if checkpoint.startswith("model_"):
            record = await execution.run_store.get(proposal_id)
            calls = record.task["acceptance_contract"]["governed_tool_sequence"]
            model_fixture = CountedModelClient(root, calls)
            models.model.model_client_factory = lambda: model_fixture
        model_provider = model_fixture if checkpoint.startswith("model_") else None
        owner, method = {
            "claim": (effects, "_recover_claim" if recovery_request is not None else "_claim"), "intent": (effects, "_intent"),
            "dispatch": (effects.connectors, "invoke_with_result"),
            "receipt": (effects, "_observe"), "publication": (effects, "_publish"),
            "model_ready": (models, "_claim"), "model_claim": (models, "_claim"),
            "model_response": (models, "_produce"), "model_result": (models, "_observe"),
            "model_publication": (models, "_publish"), "model_provider": (model_provider, "complete"),
            "model_recovery": (models.recovery, "_recover"),
        }[checkpoint]
        original = getattr(owner, method)

        async def pause_after(*args, **kwargs):
            result = None if checkpoint == "model_ready" else await original(*args, **kwargs)
            print("BT1_EFFECT_CHECKPOINT=" + checkpoint, flush=True)
            if await asyncio.to_thread(sys.stdin.readline) != "continue\n":
                raise asyncio.CancelledError("BT1_EFFECT_CONTINUATION_NOT_AUTHORIZED")
            return await original(*args, **kwargs) if checkpoint == "model_ready" else result

        setattr(owner, method, pause_after)
        if checkpoint == "model_recovery":
            response = await client.post(f"/v1/runs/{proposal_id}/model-admission/recover", json=recovery_request)
        elif checkpoint.startswith("model_"):
            response = await client.post("/v1/runs", json={"run_id": record.run_id, "task": record.task})
        else:
            response = await approve(client, proposal_id) if recovery_request is None else await client.post(
                f"/v1/approvals/{proposal_id}/effect/recover", json=recovery_request,
            )
        result = [response.status_code, response.json()]
    print("BT1_RESPONSE=" + json.dumps(result), flush=True)


@asynccontextmanager
async def paused_effect_worker(root: Path, proposal_id: str, checkpoint: str, recovery_request: dict | None = None):
    command = [sys.executable, "-m", "tests.helpers.outward_effect_worker", str(root), proposal_id, checkpoint]
    if recovery_request is not None:
        command.append(json.dumps(recovery_request))
    process = await asyncio.create_subprocess_exec(
        *command, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        while True:
            line = await asyncio.wait_for(process.stdout.readline(), timeout=20)
            assert line, (await process.stderr.read()).decode()
            if line.decode().strip() == "BT1_EFFECT_CHECKPOINT=" + checkpoint:
                break
        yield process
    finally:
        if process.returncode is None:
            process.kill()
        await asyncio.wait_for(process.communicate(), timeout=10)


async def finish_effect_worker(process):
    stdout, stderr = await asyncio.wait_for(process.communicate(b"continue\n"), timeout=20)
    assert process.returncode == 0, stderr.decode()
    return json.loads(next(line.removeprefix("BT1_RESPONSE=") for line in stdout.decode().splitlines()
                           if line.startswith("BT1_RESPONSE=")))


if __name__ == "__main__":
    asyncio.run(run(Path(sys.argv[1]), sys.argv[2], sys.argv[3], json.loads(sys.argv[4]) if len(sys.argv) > 4 else None))
