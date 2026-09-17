"""Real artifact capture, Python execution and retained SQLite acceptance evidence."""
from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import pytest

from orket.adapters.storage.card_acceptance_artifacts import CardAcceptanceArtifacts, artifact_manifest_digest
from orket.adapters.storage.card_acceptance_evidence_store import CardAcceptanceEvidenceStore
from orket.application.services.card_acceptance_service import CardAcceptanceService
from orket.core.contracts.card_acceptance_inputs import PythonCliAcceptance
from orket.core.contracts.card_completion import CompletionScope

pytestmark = pytest.mark.integration


def _definition(expected='{"answer":42}', *, arguments=(), cases=None):
    return PythonCliAcceptance(
        acceptance_ref="fixture-answer.v1", policy_ref="fixture-cli-policy.v1", workload_id="fixture-cli.v1",
        entrypoint="agent_output/main.py", artifact_paths=("agent_output/main.py",),
        cases=cases or ({"criterion_id": "answer", "description": "Exact declared JSON answer",
                         "expected_json": expected, "arguments": arguments},),
    )


async def _source(tmp_path: Path, source: str):
    output = tmp_path / "agent_output"
    await asyncio.to_thread(output.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread((output / "main.py").write_bytes, source.encode("utf-8"))


async def _verify(tmp_path: Path, definition=None, *, no_plan=False):
    store = CardAcceptanceEvidenceStore(tmp_path / "acceptance.sqlite3")
    service = CardAcceptanceService(store)
    result = await service.verify(workspace_root=tmp_path, definition=None if no_plan else definition or _definition(),
                                  card_id="card-1", run_id="run-1", attempt_id="attempt-1", workload_inputs_json='{"request":"answer"}')
    return service, store, result


@pytest.mark.asyncio
@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["lf", "crlf"])
# Layer: integration
async def test_sufficient_declared_behavior_retains_exact_inputs_artifacts_and_command_receipt(tmp_path, newline):
    source = 'print(\'{"answer":42}\')' + newline
    await _source(tmp_path, source)
    service, store, result = await _verify(tmp_path)
    assert result.decision.sufficient
    payload = json.loads(await store.read(result.evidence_digest))
    assert payload["scope"]["attempt_id"] == "attempt-1"
    assert payload["artifacts"][0]["size_bytes"] == len(source.encode())
    command = json.loads(payload["commands"][0]["result_json"])["command_results"][0]
    assert command["returncode"] == 0
    assert command["stdout_contract_ok"] is True
    assert command["stdout_encoding_valid"] is True
    assert command["stdout_truncated"] is False
    replay = await service.inspect(result.evidence_digest, definition=_definition(), scope=result.decision.scope)
    assert replay == result.decision


@pytest.mark.asyncio
@pytest.mark.parametrize("source", [
    'print(\'{"answer":0}\')\n',
    'print(\'{"answer":42}\'); raise SystemExit(1)\n',
    'def invalid syntax\n',
    'print(\'{"answer":41,"answer":42}\')\n',
    'import sys; sys.stdout.write(\'{"answer":42}\' + " " * 2000 + "bad suffix")\n',
], ids=["wrong-behavior", "failed-process", "syntax-error", "ambiguous-json", "hidden-suffix"])
# Layer: integration
async def test_unsupported_or_failed_behavior_remains_unsatisfied_with_real_evidence(tmp_path, source):
    await _source(tmp_path, source)
    _service, store, result = await _verify(tmp_path)
    assert not result.decision.sufficient
    assert result.decision.missing_criteria == ("answer",)
    assert result.decision.diagnostics
    assert await store.read(result.evidence_digest)


@pytest.mark.asyncio
# Layer: integration
async def test_no_plan_or_empty_workspace_cannot_become_success(tmp_path):
    _service, store, no_plan = await _verify(tmp_path, no_plan=True)
    assert not no_plan.decision.sufficient
    assert no_plan.evidence_digest is None
    assert not await asyncio.to_thread(store.db_path.exists)
    _service, store, empty = await _verify(tmp_path)
    assert not empty.decision.sufficient
    assert any("artifact_capture_failed" in row for row in empty.decision.diagnostics)
    assert json.loads(await store.read(empty.evidence_digest))["commands"] == []


@pytest.mark.asyncio
# Layer: integration
async def test_arguments_are_preserved_and_every_declared_case_is_executed(tmp_path):
    await _source(tmp_path, 'import json, sys; print(json.dumps(sys.argv[1:]))\n')
    definition = _definition(cases=(
        {"criterion_id": "spaces", "description": "Preserve spaces and empty arguments", "arguments": (" leading ", ""),
         "expected_json": '[" leading ",""]'},
        {"criterion_id": "second", "description": "Independent second input", "arguments": ("second",),
         "expected_json": '["second"]'},
    ))
    _service, store, result = await _verify(tmp_path, definition)
    assert result.decision.sufficient
    commands = json.loads(await store.read(result.evidence_digest))["commands"]
    assert [row["criterion_id"] for row in commands] == ["spaces", "second"]
    assert json.loads(commands[0]["result_json"])["command_results"][0]["argv"][-2:] == [" leading ", ""]


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [
    ("run_id", "another-run"), ("attempt_id", "another-attempt"), ("input_digest", "a" * 64),
])
# Layer: integration
async def test_retained_evidence_cannot_be_reused_for_another_active_scope(tmp_path, field, value):
    await _source(tmp_path, 'print(\'{"answer":42}\')\n')
    service, _store, result = await _verify(tmp_path)
    scope = CompletionScope.model_validate({**result.decision.scope.model_dump(), field: value})
    decision = await service.inspect(result.evidence_digest, definition=_definition(), scope=scope)
    assert not decision.sufficient
    assert "answer:completion_scope_mismatch" in decision.diagnostics


@pytest.mark.asyncio
# Layer: integration
async def test_modified_source_is_distinct_from_the_retained_verified_snapshot(tmp_path):
    original = 'print(\'{"answer":42}\')\n'
    await _source(tmp_path, original)
    service, store, result = await _verify(tmp_path)
    await _source(tmp_path, 'print(\'{"answer":0}\')\n')
    current = await CardAcceptanceArtifacts().capture(tmp_path, _definition().artifact_paths)
    scope = CompletionScope.model_validate({**result.decision.scope.model_dump(),
                                           "artifact_manifest_digest": artifact_manifest_digest(current)})
    stale = await service.inspect(result.evidence_digest, definition=_definition(), scope=scope)
    assert not stale.sufficient
    assert scope.artifact_manifest_digest != result.decision.scope.artifact_manifest_digest
    assert json.loads(await store.read(result.evidence_digest))["artifacts"][0]["size_bytes"] == len(original.encode())


@pytest.mark.asyncio
# Layer: integration
async def test_a_program_that_changes_its_verification_snapshot_is_rejected(tmp_path):
    await _source(tmp_path, 'from pathlib import Path; Path(__file__).write_text("changed"); print(\'{"answer":42}\')\n')
    before = await asyncio.to_thread((tmp_path / "agent_output/main.py").read_bytes)
    _service, _store, result = await _verify(tmp_path)
    assert not result.decision.sufficient
    assert "answer:verification_snapshot_changed" in result.decision.diagnostics
    assert await asyncio.to_thread((tmp_path / "agent_output/main.py").read_bytes) == before


@pytest.mark.asyncio
# Layer: integration
async def test_tampered_retained_evidence_is_rejected_without_repairing_the_store(tmp_path):
    await _source(tmp_path, 'print(\'{"answer":42}\')\n')
    service, store, result = await _verify(tmp_path)

    def tamper():
        with sqlite3.connect(store.db_path) as conn:
            conn.execute("DROP TRIGGER card_acceptance_evidence_no_update")
            conn.execute("UPDATE card_acceptance_evidence SET payload = '{}' WHERE digest = ?", (result.evidence_digest,))
    await asyncio.to_thread(tamper)
    decision = await service.inspect(result.evidence_digest, definition=_definition(), scope=result.decision.scope)
    assert not decision.sufficient
    assert any("E_CARD_ACCEPTANCE_EVIDENCE_DIGEST" in row for row in decision.diagnostics)

    def read():
        with sqlite3.connect(f"{store.db_path.as_uri()}?mode=ro", uri=True) as conn:
            return conn.execute("SELECT payload FROM card_acceptance_evidence").fetchone()[0]
    assert await asyncio.to_thread(read) == "{}"


@pytest.mark.asyncio
# Layer: integration
async def test_cancellation_drains_current_child_stops_next_case_and_cleans_snapshot(tmp_path):
    started, finished, second = (tmp_path / name for name in ("started.txt", "finished.txt", "second.txt"))
    source = (
        "from pathlib import Path\nimport sys, time\n"
        f"marker = Path({str(started)!r}) if sys.argv[1] == 'first' else Path({str(second)!r})\n"
        "marker.write_text(str(Path.cwd()))\ntime.sleep(0.3)\n"
        f"Path({str(finished)!r}).write_text('finished')\n"
        "print('{\"answer\":42}')\n"
    )
    await _source(tmp_path, source)
    definition = _definition(cases=tuple({"criterion_id": name, "description": name, "arguments": (name,),
                                         "expected_json": '{"answer":42}'} for name in ("first", "second")))
    service = CardAcceptanceService(CardAcceptanceEvidenceStore(tmp_path / "acceptance.sqlite3"))
    task = asyncio.create_task(service.verify(workspace_root=tmp_path, definition=definition, card_id="card-1",
                                             run_id="run-1", attempt_id="attempt-1", workload_inputs_json='{}'))
    async with asyncio.timeout(5):
        while not await asyncio.to_thread(started.exists):  # noqa: ASYNC110 - The real child signals through this file.
            await asyncio.sleep(0.01)
    task.cancel()
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await asyncio.to_thread(finished.exists)
    assert not await asyncio.to_thread(second.exists)
    snapshot_root = Path(await asyncio.to_thread(started.read_text))
    assert not await asyncio.to_thread(snapshot_root.exists)

    def retained():
        with sqlite3.connect(service.evidence_store.db_path) as conn:
            return conn.execute("SELECT digest, payload FROM card_acceptance_evidence").fetchone()
    digest, body = await asyncio.to_thread(retained)
    package = json.loads(body)
    assert len(package["commands"]) == 1
    decision = await service.inspect(digest, definition=definition, scope=CompletionScope.model_validate(package["scope"]))
    assert not decision.sufficient
    assert "verification_cancelled" in decision.diagnostics


@pytest.mark.asyncio
# Layer: integration
async def test_verification_child_does_not_inherit_unadmitted_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_ACCEPTANCE_TEST_SECRET", "local-test-secret")
    await _source(tmp_path, 'import json, os; print(json.dumps({"inherited": "ORKET_ACCEPTANCE_TEST_SECRET" in os.environ}))\n')
    _service, store, result = await _verify(tmp_path, _definition('{"inherited":false}'))
    assert result.decision.sufficient
    assert "local-test-secret" not in await store.read(result.evidence_digest)


@pytest.mark.asyncio
# Layer: integration
async def test_actual_artifact_limit_refuses_execution_and_missing_evidence_store_stays_absent(tmp_path):
    await _source(tmp_path, "#" * 1_048_577)
    service, _store, result = await _verify(tmp_path)
    assert not result.decision.sufficient
    assert any("E_CARD_ACCEPTANCE_ARTIFACT_LIMIT" in row for row in result.decision.diagnostics)
    missing = tmp_path / "missing.sqlite3"
    reader = CardAcceptanceService(CardAcceptanceEvidenceStore(missing))
    inspected = await reader.inspect("a" * 64, definition=_definition(), scope=result.decision.scope)
    assert not inspected.sufficient
    assert not await asyncio.to_thread(missing.exists)


@pytest.mark.asyncio
# Layer: integration
async def test_evidence_store_enforces_actual_body_limit_and_immutable_rows(tmp_path):
    store = CardAcceptanceEvidenceStore(tmp_path / "evidence.sqlite3")
    digest = await store.put("{}")
    assert await store.put("{}") == digest

    def update():
        with sqlite3.connect(store.db_path) as conn:
            conn.execute("UPDATE card_acceptance_evidence SET payload = 'changed' WHERE digest = ?", (digest,))
    with pytest.raises(sqlite3.IntegrityError, match="E_CARD_ACCEPTANCE_EVIDENCE_IMMUTABLE"):
        await asyncio.to_thread(update)
    with pytest.raises(ValueError, match="E_CARD_ACCEPTANCE_EVIDENCE_LIMIT"):
        await store.put(" " * 33_554_433)

    def oversized():
        with sqlite3.connect(store.db_path) as conn:
            conn.execute("INSERT INTO card_acceptance_evidence VALUES (?, zeroblob(?))", ("b" * 64, 33_554_433))
    await asyncio.to_thread(oversized)
    with pytest.raises(ValueError, match="E_CARD_ACCEPTANCE_EVIDENCE_LIMIT"):
        await store.read("b" * 64)
    assert await store.read(digest) == "{}"


@pytest.mark.asyncio
# Layer: integration
async def test_artifact_snapshot_enforces_actual_aggregate_limit_and_root_containment(tmp_path):
    output = tmp_path / "agent_output"
    await asyncio.to_thread(output.mkdir)
    paths = tuple(f"agent_output/file{index}.txt" for index in range(9))
    for path in paths:
        await asyncio.to_thread((tmp_path / path).write_bytes, b"x" * 1_048_576)
    artifacts = CardAcceptanceArtifacts()
    with pytest.raises(ValueError, match="E_CARD_ACCEPTANCE_ARTIFACT_LIMIT"):
        await artifacts.capture(tmp_path, paths)
    with pytest.raises(ValueError, match="E_CARD_ACCEPTANCE_ARTIFACT_ESCAPE"):
        await artifacts.capture(tmp_path, ("../outside.txt",))
