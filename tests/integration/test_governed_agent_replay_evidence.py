"""Layer: integration. Real SQLite publication, corruption, and public CLI replay."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from orket.adapters.storage.async_governed_agent_repository import AsyncGovernedAgentRepository
from orket.adapters.storage.governed_agent_replay_store import GovernedAgentReplayStore
from orket.application.services.governed_agent_inspection_service import GovernedAgentInspectionService
from orket.core.contracts.governed_agent_ports import GovernedAgentInvocationOutcome
from orket.core.domain.governed_agent_continuation import decide_governed_agent_continuation
from orket.interfaces.orket_bundle_cli import main
from orket.interfaces.runtime_entrypoints import create_api_app
from orket.runtime import CompositionConfig
from orket_extension_sdk.agent_fixtures import agent_iteration_result, prefixed_digest
from tests.interfaces.test_governed_agent_api import _configure_api, _headers
from tests.interfaces.test_governed_agent_cli import _decision_inputs
from tests.runtime.governed_agent_test_support import agent_request, binding_for, prepare_authority

pytestmark = pytest.mark.integration


async def _prepare(path: Path, count: int = 3) -> None:
    for ordinal in range(1, count + 1):
        request = agent_request()
        request["identity"].update(step_id=f"step-{ordinal}", invocation_id=f"invocation-{ordinal}",
                                   iteration_ordinal=ordinal)
        binding = binding_for(request)
        repository = await prepare_authority(path, request, binding)
        result = agent_iteration_result()
        result["identity"] = request["identity"]
        result["model_receipts"] = []
        result["effect_proposals"] = []
        for field in ("progress_claims", "memory_write_proposals"):
            for item in result[field]:
                item["identity"] = request["identity"]
        for key in ("model_calls", "input_tokens", "output_tokens", "charged_input_tokens", "charged_output_tokens",
                    "effect_proposals"):
            result["usage"][key] = 0
        digest = prefixed_digest(result)
        outcome = GovernedAgentInvocationOutcome("returned", binding, result, digest, None, True)
        assert (await repository.accept_result(outcome=outcome)).status == "accepted"
        inputs = _decision_inputs()
        decision = decide_governed_agent_continuation(inputs)
        assert (await repository.publish_continuation_decision(
            binding=binding, accepted_result_digest=digest, decision_inputs=inputs.to_payload(),
            decision_payload=decision.to_payload(),
        )).status == "accepted"


def _inspector(path: Path) -> GovernedAgentInspectionService:
    repository = AsyncGovernedAgentRepository(path)
    return GovernedAgentInspectionService(
        iteration_repository=repository,
        call_repository=repository,
        replay_repository=GovernedAgentReplayStore(path),
    )


def _dump(path: Path) -> tuple[str, ...]:
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as connection:
        return tuple(connection.iterdump())


@pytest.mark.parametrize("count", [1, 3])
# Layer: integration
def test_complete_replay_compares_all_expected_decisions_without_writes(tmp_path: Path, capsys, count: int) -> None:
    path = tmp_path / "agent.sqlite3"
    asyncio.run(_prepare(path, count))
    before = _dump(path)
    assert main(["agent", "replay", "run-1", "--db", str(path), "--json"]) == 0
    replay = json.loads(capsys.readouterr().out)
    assert replay["schema_version"] == "governed_agent_replay.v2"
    assert replay["status"] == "matched"
    assert replay["expected_count"] == replay["compared_count"] == replay["matched_count"] == count
    assert replay["scope"] == "recorded_continuation_decisions"
    assert replay["external_effects_verified"] is replay["full_execution_verified"] is False
    assert _dump(path) == before


@pytest.mark.parametrize("ordinal", [1, 2, 3])
# Layer: integration
def test_missing_snapshot_never_matches_surviving_subset(tmp_path: Path, capsys, ordinal: int) -> None:
    path = tmp_path / "agent.sqlite3"
    asyncio.run(_prepare(path))
    with sqlite3.connect(path) as connection:
        connection.execute("DELETE FROM governed_agent_invocations WHERE invocation_id = ?", (f"invocation-{ordinal}",))
    before = _dump(path)
    assert main(["agent", "replay", "run-1", "--db", str(path), "--json"]) != 0
    replay = json.loads(capsys.readouterr().out)
    assert replay["status"] == "insufficient_evidence"
    assert replay["expected_count"] == 3 and replay["compared_count"] == 2
    assert f"snapshot_missing:step-{ordinal}" in replay["diagnostics"]
    assert _dump(path) == before


@pytest.mark.parametrize("column,value,status", [
    ("decision_inputs_json", None, "insufficient_evidence"),
    ("decision_inputs_digest", None, "insufficient_evidence"),
    ("decision_digest", "sha256:" + "0" * 64, "mismatch"),
    ("result_digest", "sha256:" + "0" * 64, "mismatch"),
    ("request_json", "{}", "mismatch"),
    ("decision_inputs_json", "{}", "mismatch"),
    ("decision_inputs_json", "invalid-json", "mismatch"),
])
# Layer: integration
def test_missing_or_corrupt_evidence_fails_closed(tmp_path: Path, column: str, value: str | None, status: str) -> None:
    path = tmp_path / "agent.sqlite3"
    asyncio.run(_prepare(path, 1))
    with sqlite3.connect(path) as connection:
        connection.execute(f"UPDATE governed_agent_invocations SET {column} = ?", (value,))
    before = _dump(path)
    replay = asyncio.run(_inspector(path).replay(run_id="run-1"))
    assert replay["status"] == status
    assert replay["compared_count"] == 0
    assert _dump(path) == before


# Layer: integration
def test_missing_database_replay_creates_no_files(tmp_path: Path) -> None:
    path = tmp_path / "missing.sqlite3"
    assert asyncio.run(_inspector(path).replay(run_id="run-1")) is None
    assert list(tmp_path.iterdir()) == []


# Layer: integration
def test_empty_invocation_table_cannot_hide_expected_history(tmp_path: Path) -> None:
    path = tmp_path / "agent.sqlite3"
    asyncio.run(_prepare(path))
    with sqlite3.connect(path) as connection:
        connection.execute("DELETE FROM governed_agent_invocations")
    before = _dump(path)
    replay = asyncio.run(_inspector(path).replay(run_id="run-1"))
    assert replay["status"] == "insufficient_evidence"
    assert replay["expected_count"] == 3 and replay["compared_count"] == 0
    assert _dump(path) == before


@pytest.mark.parametrize("damage", ["missing_tail", "missing_inputs", "corrupt_digest"])
# Layer: integration
def test_authenticated_api_reports_incomplete_or_invalid_replay(tmp_path: Path, monkeypatch, damage: str) -> None:
    path = tmp_path / "agent.sqlite3"
    asyncio.run(_prepare(path))
    with sqlite3.connect(path) as connection:
        if damage == "missing_tail":
            connection.execute("DELETE FROM governed_agent_invocations WHERE invocation_id = 'invocation-3'")
        elif damage == "missing_inputs":
            connection.execute("UPDATE governed_agent_invocations SET decision_inputs_json = NULL")
        else:
            connection.execute("UPDATE governed_agent_invocations SET decision_digest = 'corrupt'")
    _configure_api(monkeypatch, path, enabled=False)
    with TestClient(create_api_app(CompositionConfig(project_root=tmp_path))) as client:
        before = _dump(path)
        route = "/v1/agent-runs/run-1/replay"
        assert client.get(route).status_code == 403
        response = client.get(route, headers=_headers())
        assert response.status_code == 200
        replay = response.json()
        assert replay["status"] == ("mismatch" if damage == "corrupt_digest" else "insufficient_evidence")
        assert replay["expected_count"] == 3
        assert _dump(path) == before


# Layer: integration
async def test_replay_uses_one_read_transaction_during_concurrent_delete(tmp_path: Path, monkeypatch) -> None:
    from orket.adapters.storage import governed_agent_replay_store as storage

    path = tmp_path / "agent.sqlite3"
    await _prepare(path)
    original = storage._iterations

    async def delete_after_inventory(conn, run_id):
        def delete_tail():
            with sqlite3.connect(path) as connection:
                connection.execute("DELETE FROM governed_agent_invocations WHERE invocation_id = 'invocation-3'")
        await asyncio.to_thread(delete_tail)
        return await original(conn, run_id)

    monkeypatch.setattr(storage, "_iterations", delete_after_inventory)
    retained = await _inspector(path).replay(run_id="run-1")
    assert retained["status"] == "matched"
    assert retained["expected_count"] == retained["compared_count"] == 3
    monkeypatch.setattr(storage, "_iterations", original)
    subsequent = await _inspector(path).replay(run_id="run-1")
    assert subsequent["status"] == "insufficient_evidence"
    assert subsequent["compared_count"] == 2


# Layer: integration
def test_legacy_inputs_are_not_sealed_by_replay_or_schema_initialization(tmp_path: Path) -> None:
    path = tmp_path / "agent.sqlite3"
    asyncio.run(_prepare(path, 1))
    with sqlite3.connect(path) as connection:
        connection.execute("ALTER TABLE governed_agent_invocations DROP COLUMN decision_inputs_digest")
    before = _dump(path)
    legacy = asyncio.run(_inspector(path).replay(run_id="run-1"))
    assert legacy["status"] == "insufficient_evidence"
    assert legacy["decisions"][0]["missing_fields"] == ["decision_inputs_digest"]
    assert _dump(path) == before

    async def initialize_concurrently():
        await asyncio.gather(*(AsyncGovernedAgentRepository(path).get_iteration_snapshot(invocation_id="invocation-1")
                               for _ in range(2)))

    asyncio.run(initialize_concurrently())
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT decision_inputs_digest FROM governed_agent_invocations").fetchone() == (None,)
    assert asyncio.run(_inspector(path).replay(run_id="run-1"))["status"] == "insufficient_evidence"


@pytest.mark.parametrize("target,field,value", [
    ("binding_json", "run_id", "another-run"),
    ("binding_json", "step_id", ["step-1"]),
    ("binding_json", "invocation_id", "another-invocation"),
    ("request_json", "identity", []),
    ("decision_inputs_json", "accepted_cancel", "false"),
])
# Layer: integration
def test_substituted_or_malformed_identity_never_matches(tmp_path: Path, target: str, field: str, value) -> None:
    path = tmp_path / "agent.sqlite3"
    asyncio.run(_prepare(path, 1))
    with sqlite3.connect(path) as connection:
        payload = json.loads(connection.execute(f"SELECT {target} FROM governed_agent_invocations").fetchone()[0])
        payload[field] = value
        connection.execute(f"UPDATE governed_agent_invocations SET {target} = ?", (json.dumps(payload),))
        if target == "decision_inputs_json":
            connection.execute("UPDATE governed_agent_invocations SET decision_inputs_digest = ?", (prefixed_digest(payload),))
    before = _dump(path)
    replay = asyncio.run(_inspector(path).replay(run_id="run-1"))
    assert replay["status"] in {"mismatch", "insufficient_evidence"}
    assert replay["matched_count"] == 0
    assert _dump(path) == before


@pytest.mark.parametrize("limit", ["rows", "bytes"])
# Layer: integration
def test_actual_replay_resource_limits_refuse_a_partial_comparison(tmp_path: Path, limit: str) -> None:
    path = tmp_path / "agent.sqlite3"
    asyncio.run(_prepare(path, 1))
    with sqlite3.connect(path) as connection:
        if limit == "rows":
            connection.execute("""
                WITH RECURSIVE n(value) AS (SELECT 1 UNION ALL SELECT value + 1 FROM n WHERE value < 10000)
                INSERT INTO governed_agent_invocations (invocation_id, binding_json, request_json, state)
                SELECT 'resource-' || value, binding_json, request_json, state
                FROM n CROSS JOIN governed_agent_invocations WHERE invocation_id = 'invocation-1'
            """)
        else:
            connection.execute("UPDATE governed_agent_invocations SET request_json = request_json || ?",
                               (" " * (64 * 1024 * 1024),))
    replay = asyncio.run(_inspector(path).replay(run_id="run-1"))
    assert replay["status"] == "insufficient_evidence"
    assert replay["expected_count"] is None and replay["compared_count"] == 0
    assert "replay_evidence_resource_limit" in replay["diagnostics"]


# Layer: integration
def test_missing_step_inventory_reports_unknown_count(tmp_path: Path) -> None:
    path = tmp_path / "agent.sqlite3"
    asyncio.run(_prepare(path, 1))
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TABLE control_plane_steps")
    before = _dump(path)
    replay = asyncio.run(_inspector(path).replay(run_id="run-1"))
    assert replay["status"] == "insufficient_evidence"
    assert replay["expected_count"] is None
    assert "step_inventory_missing" in replay["diagnostics"]
    assert _dump(path) == before


# Layer: integration
def test_human_cli_reports_missing_history_and_failed_status(tmp_path: Path, capsys) -> None:
    path = tmp_path / "agent.sqlite3"
    asyncio.run(_prepare(path))
    with sqlite3.connect(path) as connection:
        connection.execute("DELETE FROM governed_agent_invocations WHERE invocation_id = 'invocation-3'")
    assert main(["agent", "replay", "run-1", "--db", str(path)]) == 1
    output = capsys.readouterr().out
    assert "status=insufficient_evidence" in output
    assert "compared=2/3" in output and "snapshot_missing:step-3" in output
