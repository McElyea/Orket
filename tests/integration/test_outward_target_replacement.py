"""Real filesystem target changes across outward authorization and dispatch."""

from __future__ import annotations

import asyncio

import pytest

from tests.helpers.outward_authorization import approve, effect_snapshot, outward_api, submit_sequence
from tests.helpers.outward_authorization import boundary as boundary
from tests.helpers.outward_effect_worker import finish_effect_worker, paused_effect_worker


def _targets(root):
    original, replacement, alias = root / "original", root / "replacement", root / "alias"
    original.mkdir()
    replacement.mkdir()
    alias.symlink_to(original, target_is_directory=True)
    assert alias.is_symlink() and alias.resolve() == original
    return original, replacement, alias


def _retarget(alias, replacement):
    assert alias.is_symlink() and replacement.resolve().is_relative_to(alias.parent.resolve())
    alias.unlink()
    alias.symlink_to(replacement, target_is_directory=True)
    assert alias.resolve() == replacement


@pytest.mark.integration
@pytest.mark.parametrize("checkpoint", ["submitted", "claim", "intent"])
# Layer: integration
async def test_replaced_target_cannot_receive_an_approved_write(tmp_path, boundary, checkpoint):
    """Real worker pause and symlink replacement must not redirect the bound write, including after intent."""
    db_path, inputs, calls = boundary
    original, replacement, alias = await asyncio.to_thread(_targets, tmp_path)
    calls[0]["args"]["path"] = "alias/output.txt"
    try:
        async with outward_api(tmp_path, inputs) as (client, context):
            proposal_id = await submit_sequence(client, calls[:1])
            proposal = await context.outward_approval_store.get(proposal_id)
            assert proposal.authorization.target_ref == str(original / "output.txt")
            if checkpoint == "submitted":
                await asyncio.to_thread(_retarget, alias, replacement)
                response = await approve(client, proposal_id)
                status, payload = response.status_code, response.json()
            else:
                async with paused_effect_worker(tmp_path, proposal_id, checkpoint) as worker:
                    await asyncio.to_thread(_retarget, alias, replacement)
                    status, payload = await finish_effect_worker(worker)
            assert not await asyncio.to_thread((replacement / "output.txt").exists), payload
            assert not await asyncio.to_thread((original / "output.txt").exists), payload
            assert status == 409, payload
            events = await context.outward_run_event_store.list_for_run("bt0-run")
            assert not any(event.event_type == "tool_invoked" for event in events)
        effect, journal = await effect_snapshot(db_path, proposal_id)
        assert (effect.state if effect else None) == {"submitted": None, "claim": "claimed", "intent": "dispatching"}[checkpoint]
        assert len(journal) == {"submitted": 0, "claim": 1, "intent": 2}[checkpoint]
        async with outward_api(tmp_path, inputs) as (client, _context):
            assert (await approve(client, proposal_id)).status_code == 409
        assert not await asyncio.to_thread((replacement / "output.txt").exists)
    finally:
        if await asyncio.to_thread(alias.is_symlink):
            await asyncio.to_thread(alias.unlink)


@pytest.mark.integration
# Layer: integration
async def test_unchanged_link_target_receives_one_approved_write(tmp_path, boundary):
    """Healthy opposite: the admitted link remains usable and the observed receipt names its bound target."""
    db_path, inputs, calls = boundary
    original, replacement, alias = await asyncio.to_thread(_targets, tmp_path)
    calls[0]["args"]["path"] = "alias/output.txt"
    try:
        async with outward_api(tmp_path, inputs) as (client, _context):
            proposal_id = await submit_sequence(client, calls[:1])
            async with paused_effect_worker(tmp_path, proposal_id, "intent") as worker:
                status, payload = await finish_effect_worker(worker)
            assert status == 200, payload
        assert await asyncio.to_thread((original / "output.txt").read_text) == calls[0]["args"]["content"]
        assert not await asyncio.to_thread((replacement / "output.txt").exists)
        effect, journal = await effect_snapshot(db_path, proposal_id)
        assert effect.state == "published" and len(journal) == 4
        assert effect.receipt["result"]["path"] == str(original / "output.txt")
    finally:
        if await asyncio.to_thread(alias.is_symlink):
            await asyncio.to_thread(alias.unlink)
