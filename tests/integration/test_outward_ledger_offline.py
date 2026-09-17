from __future__ import annotations

import asyncio
import json
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from orket.core.domain.outward_ledger import GENESIS_CHAIN_HASH, chain_hash_for, verify_ledger_export
from tests.helpers.outward_ledger import ledger_event, logical_contents, seed_ledger


@pytest.mark.integration
@pytest.mark.asyncio
# Layer: integration. Run the actual offline CLI against a real export and its corrupted copy.
async def test_offline_cli_verifies_file_without_claiming_retained_integrity(tmp_path) -> None:
    db_path = tmp_path / "offline.sqlite3"
    service = await seed_ledger(db_path, 3)
    exported = await service.export("bt2")
    before = await asyncio.to_thread(logical_contents, db_path)
    root = await asyncio.to_thread(lambda: Path(__file__).resolve().parents[2])
    for corrupt in (False, True):
        payload = deepcopy(exported)
        if corrupt:
            payload["events"][0]["payload"]["position"] = 999
        path = tmp_path / f"export-{corrupt}.json"
        await asyncio.to_thread(path.write_text, json.dumps(payload), encoding="utf-8")
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "orket.interfaces.orket_bundle_cli", "ledger", "verify", str(path),
            cwd=root, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=20)
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
        assert process.returncode == (1 if corrupt else 0), stderr.decode()
        report = json.loads(stdout)
        assert report["result"] == ("invalid" if corrupt else "valid")
        assert report["verification_scope"] == "export_self_consistency"
        assert report["retained_integrity"] == report["snapshot_completeness"] == "not_verified"
    assert await asyncio.to_thread(logical_contents, db_path) == before


@pytest.mark.integration
@pytest.mark.asyncio
# Layer: integration. A self-consistent rehash of reversed real events still violates v1 ordering.
async def test_rehashed_v1_export_cannot_redefine_canonical_event_order(tmp_path) -> None:
    service = await seed_ledger(tmp_path / "order.sqlite3", 3)
    payload = await service.export("bt2")
    payload["events"].reverse()
    previous = GENESIS_CHAIN_HASH
    for position, event in enumerate(payload["events"], start=1):
        event["position"], event["previous_chain_hash"] = position, previous
        event["chain_hash"] = chain_hash_for(previous, event["event_hash"])
        previous = event["chain_hash"]
    payload["canonical"]["ledger_hash"] = previous
    report = verify_ledger_export(payload)
    assert report["result"] == "invalid"
    assert any("canonical event order mismatch" in error for error in report["errors"])


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["negative_count", "huge_count", "bad_turn", "bad_genesis", "duplicate_span", "huge_span"])
# Layer: integration. Corrupt actual full/filtered exports before invoking the offline verifier.
async def test_malformed_export_returns_diagnostics_without_unbounded_traversal(tmp_path, mutation) -> None:
    service = await seed_ledger(tmp_path / "malformed.sqlite3", 3)
    await service.event_store.append(replace(ledger_event(4), event_type="proposal_made"))
    partial = mutation in {"duplicate_span", "huge_span"}
    payload = await service.export("bt2", types=("proposals",)) if partial else await service.export("bt2")
    if mutation in {"negative_count", "huge_count"}:
        payload["canonical"]["event_count"] = -1 if mutation == "negative_count" else 10**20
    elif mutation == "bad_turn":
        payload["events"][0]["turn"] = {}
    elif mutation == "bad_genesis":
        payload["canonical"]["genesis"] = []
    elif mutation == "duplicate_span":
        payload["omitted_spans"].append(deepcopy(payload["omitted_spans"][0]))
    else:
        payload["omitted_spans"][0]["to_position"] = 10**20
    report = verify_ledger_export(payload)
    assert report["result"] == "invalid" and report["errors"]


@pytest.mark.integration
@pytest.mark.asyncio
# Layer: integration. Removing identity from a real empty-run export cannot remain valid.
async def test_empty_export_requires_run_identity(tmp_path) -> None:
    service = await seed_ledger(tmp_path / "empty.sqlite3", 0)
    payload = await service.export("bt2")
    assert verify_ledger_export(payload)["result"] == "valid"
    del payload["run_id"]
    report = verify_ledger_export(payload)
    assert report["result"] == "invalid" and "run_id must be a nonempty string" in report["errors"]
