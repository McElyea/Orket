"""Fixtures that obtain completion through real Python checks and SQLite writes."""
from __future__ import annotations

import asyncio
from pathlib import Path

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.adapters.storage.card_acceptance_evidence_store import CardAcceptanceEvidenceStore
from orket.application.services.card_acceptance_service import CardAcceptanceService
from orket.application.services.card_completion_service import CardCompletionService
from orket.core.contracts.card_acceptance_inputs import ArtifactAcceptance, PythonCliAcceptance
from orket.schema import CardStatus

SOURCE = 'import json, sys\nprint(json.dumps({"answer": int(sys.argv[1]) + 1}))\n'


def text_acceptance(path: str, expected_text: str, *, workload_id: str) -> ArtifactAcceptance:
    return ArtifactAcceptance(
        schema_version="card_artifact_acceptance.v1", acceptance_ref=f"{workload_id}.acceptance.v1",
        policy_ref="literal-artifact-text.v1", workload_id=workload_id, artifact_paths=(path,),
        cases=({"kind": "text_equals", "criterion_id": "literal-content", "description": "Exact declared UTF-8 text",
                "path": path, "expected_text": expected_text},),
    )


def completion_definition():
    return PythonCliAcceptance(
        acceptance_ref="increment.v1", policy_ref="increment-cases.v1", workload_id="increment-cli.v1",
        entrypoint="agent_output/main.py", artifact_paths=("agent_output/main.py",),
        cases=({"criterion_id": "positive", "description": "Increment positive integer", "arguments": ("41",),
                "expected_json": '{"answer":42}'},
               {"criterion_id": "negative", "description": "Increment negative integer", "arguments": ("-1",),
                "expected_json": '{"answer":0}'}),
    )


async def write_completion_source(workspace: Path, source: str = SOURCE):
    path = workspace / "agent_output" / "main.py"
    await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(path.write_bytes, source.encode("utf-8"))


def completion_components(db_path, workspace):
    store = CardAcceptanceEvidenceStore(Path(db_path).with_suffix(".acceptance.sqlite3"))
    service = CardCompletionService(workspace_root=workspace, acceptance=CardAcceptanceService(store))
    return AsyncCardRepository(db_path, completion_authority=service), service


async def prepare_existing_card(repo, card_id, workspace, *, service=None):
    record = await repo.get_by_id(card_id)
    record.params["completion_acceptance"] = completion_definition().model_dump(mode="json")
    await repo.save(record)
    await write_completion_source(workspace)
    configured = repo
    if service is None:
        configured, service = completion_components(repo.db_path, workspace)
    context = await service.begin_attempt(configured, card_id=card_id, run_id="fixture-run", attempt_id="fixture-attempt")
    evaluation = await service.evaluate_attempt(configured, context)
    assert evaluation.decision.sufficient
    return configured, service, context, evaluation


async def complete_existing_card(repo, card_id, workspace, *, service=None, target_status=CardStatus.DONE):
    configured, service, context, evaluation = await prepare_existing_card(repo, card_id, workspace, service=service)
    await configured.update_status(card_id, target_status, completion_request=evaluation.request)
    return configured, service, context, evaluation
