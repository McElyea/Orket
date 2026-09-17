"""Artifact checks use actual bytes and retained stores, without executing outputs."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json

import pytest

from orket.core.contracts.card_acceptance_inputs import ArtifactAcceptance, CardAcceptancePackage
from orket.core.contracts.card_completion_commit import CardCompletionRejected
from orket.core.domain.records import IssueRecord
from orket.schema import CardStatus
from tests.helpers.card_completion import completion_components, text_acceptance

pytestmark = pytest.mark.integration


async def _prepare(tmp_path, definition, content):
    repo, service = completion_components(tmp_path / "cards.db", tmp_path / "workspace")
    path = service.workspace_root / definition.artifact_paths[0]
    await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
    if content is not None:
        await asyncio.to_thread(path.write_bytes, content)
    await repo.save(IssueRecord(id="card", summary="Declared artifact", seat="developer", build_id="build",
                               params={"completion_acceptance": definition.model_dump(mode="json")}))
    context = await service.begin_attempt(repo, card_id="card", run_id="run", attempt_id="attempt")
    evaluated = await service.evaluate_attempt(repo, context)
    return repo, service, path, evaluated


@pytest.mark.asyncio
@pytest.mark.parametrize("content,accepted", [
    (b"exact\n", True), (b"exact\r\n", False), (b"wrong\n", False), (b"exact\n\xff", False), (None, False),
])
# Layer: integration
async def test_text_acceptance_reaches_storage_only_for_exact_declared_bytes(tmp_path, content, accepted):
    definition = text_acceptance("agent_output/result.txt", "exact\n", workload_id="literal-file")
    repo, service, path, evaluated = await _prepare(tmp_path, definition, content)
    assert evaluated.decision.sufficient is accepted
    if not accepted:
        with pytest.raises(CardCompletionRejected):
            await repo.update_status("card", CardStatus.DONE, completion_request=evaluated.request)
        assert (await repo.get_by_id("card")).status == CardStatus.READY
        return
    receipt = await repo.update_status("card", CardStatus.DONE, completion_request=evaluated.request)
    package = CardAcceptancePackage.model_validate_json(await service.acceptance.evidence_store.read(evaluated.request.evidence_digest))
    assert package.schema_version == "card_acceptance_package.v2" and package.commands == ()
    assert package.plan.requirements[0].evidence_class.value == "artifact_verification"
    assert json.loads(package.inputs_json)["runtime"] == {"verifier": "card_artifact_verifier.v1"}
    before = await asyncio.to_thread(service.acceptance.evidence_store.db_path.read_bytes)
    await asyncio.to_thread(path.unlink)
    assert await repo.read_completion_receipt("card") == receipt
    assert await asyncio.to_thread(service.acceptance.evidence_store.db_path.read_bytes) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("content,expected,accepted", [
    (b'{"decision":{"mode":"monolith"},"notes":"kept"}', '"monolith"', True),
    (b'{"decision":{"mode":"other"}}', '"monolith"', False),
    (b'{"decision":{"mode":true}}', '1', False),
    (b'{"decision":{"mode":"wrong","mode":"monolith"}}', '"monolith"', False),
    (b'{"decision":[]}', '"monolith"', False),
    (b'{"decision":{"mode":"monolith"}} trailing', '"monolith"', False),
])
# Layer: integration
async def test_json_artifact_checks_only_declared_object_value_with_strict_json(tmp_path, content, expected, accepted):
    definition = ArtifactAcceptance(
        schema_version="card_artifact_acceptance.v1", acceptance_ref="design.v1", policy_ref="design-fields.v1",
        workload_id="design", artifact_paths=("agent_output/design.json",), cases=({
            "kind": "json_value_equals", "criterion_id": "mode", "description": "Chosen architecture",
            "path": "agent_output/design.json", "key_path": ("decision", "mode"), "expected_json": expected,
        },),
    )
    repo, _service, _path, evaluated = await _prepare(tmp_path, definition, content)
    assert evaluated.decision.sufficient is accepted
    if accepted:
        await repo.update_status("card", CardStatus.GUARD_APPROVED, completion_request=evaluated.request)
        assert await repo.read_completion_receipt("card") is not None


@pytest.mark.asyncio
# Layer: integration
async def test_artifact_mutation_and_resealed_failed_evidence_cannot_authorize_completion(tmp_path):
    definition = text_acceptance("agent_output/result.txt", "accepted", workload_id="literal-file")
    repo, service, path, evaluated = await _prepare(tmp_path, definition, b"accepted")
    await asyncio.to_thread(path.write_bytes, b"changed")
    with pytest.raises(CardCompletionRejected):
        await repo.update_status("card", CardStatus.DONE, completion_request=evaluated.request)
    body = json.loads(await service.acceptance.evidence_store.read(evaluated.request.evidence_digest))
    artifact = body["artifacts"][0]
    artifact.update(content_base64=base64.b64encode(b"changed").decode(), size_bytes=7,
                    sha256=hashlib.sha256(b"changed").hexdigest())
    from orket.adapters.storage.card_acceptance_artifacts import CapturedCardArtifact, artifact_manifest_digest
    body["scope"]["artifact_manifest_digest"] = artifact_manifest_digest((CapturedCardArtifact(path=artifact["path"], content=b"changed"),))
    digest = await service.acceptance.evidence_store.put(json.dumps(body))
    # Even a self-consistent retained body is compared with the independently declared criterion.
    from orket.core.contracts.card_completion import CompletionScope
    decision = await service.acceptance.inspect(digest, definition=definition, scope=CompletionScope.model_validate(body["scope"]))
    assert not decision.sufficient and decision.state.value == "acceptance_failed"


@pytest.mark.parametrize("change", [
    {"schema_version": "unknown"}, {"artifact_paths": ("../result.txt",)},
    {"artifact_paths": ("agent_output/other.txt",)}, {"cases": ()},
])
# Layer: contract
def test_artifact_definition_rejects_unsupported_or_incomplete_criteria(change):
    raw = text_acceptance("agent_output/result.txt", "literal", workload_id="literal-file").model_dump(mode="json")
    with pytest.raises(ValueError):
        ArtifactAcceptance.model_validate({**raw, **change})


@pytest.mark.asyncio
# Layer: integration
async def test_artifact_acceptance_never_executes_declared_python_output(tmp_path):
    sentinel = tmp_path / "unexpected-execution"
    source = f"from pathlib import Path\nPath({str(sentinel)!r}).write_bytes(b'executed')\n"
    definition = text_acceptance("agent_output/main.py", source, workload_id="python-as-text")
    repo, service, _path, evaluated = await _prepare(tmp_path, definition, source.encode("utf-8"))
    receipt = await repo.update_status("card", CardStatus.DONE, completion_request=evaluated.request)
    assert await repo.read_completion_receipt("card") == receipt
    assert not await asyncio.to_thread(sentinel.exists)
    body = json.loads(await service.acceptance.evidence_store.read(evaluated.request.evidence_digest))
    assert body["commands"] == []
    with pytest.raises(ValueError):
        CardAcceptancePackage.model_validate({**body, "schema_version": "card_acceptance_package.v1"})
