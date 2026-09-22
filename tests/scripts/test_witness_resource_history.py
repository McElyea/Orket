"""Layer: integration. Checkpoint resource history comes from real SQLite records."""

from types import SimpleNamespace

import pytest

from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.core.contracts.control_plane_models import ResourceRecord
from scripts.proof.trusted_run_witness_support import _checkpoint_resource
from tests.helpers.trusted_run_witness_fixtures import valid_bundle

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def resource_record(value):
    return ResourceRecord.model_validate(
        {
            "resource_kind": "turn_tool_namespace",
            "ownership_class": "run_owned",
            "last_observed_timestamp": "2026-01-01T00:00:00+00:00",
            "cleanup_authority_class": "runtime_cleanup_allowed",
            "reconciliation_status": "governed_execution_authority",
            **value,
        }
    )


@pytest.mark.parametrize("unrelated", ["missing", "other-lease", "other-resource"])
async def test_checkpoint_resource_refuses_unbound_history(tmp_path, unrelated):
    repository = AsyncControlPlaneRecordRepository(tmp_path / "actual.sqlite3")
    authority = valid_bundle()["authority_lineage"]
    value = authority["resource"]
    if unrelated == "other-lease":
        value["provenance_ref"] = "lease:unrelated"
    if unrelated == "other-resource":
        value["resource_id"] = "namespace:unrelated"
    if unrelated != "missing":
        await repository.save_resource_record(record=resource_record(value))
    with pytest.raises(ValueError, match="trusted_run_checkpoint_resource_history_missing"):
        await _checkpoint_resource(SimpleNamespace(control_plane_repository=repository), authority["checkpoint"])


async def test_checkpoint_resource_uses_latest_matching_record_without_rewriting_history(tmp_path):
    repository = AsyncControlPlaneRecordRepository(tmp_path / "actual.sqlite3")
    authority = valid_bundle()["authority_lineage"]
    first = resource_record(authority["resource"])
    second = first.model_copy(update={"current_observed_state": first.current_observed_state + ";released"})
    unrelated = first.model_copy(update={"provenance_ref": "lease:unrelated", "current_observed_state": "later turn"})
    for record in (first, second, unrelated):
        await repository.save_resource_record(record=record)
    before = await repository.list_resource_records(resource_id=first.resource_id)
    selected = await _checkpoint_resource(SimpleNamespace(control_plane_repository=repository), authority["checkpoint"])
    assert selected == second.model_dump(mode="json")
    assert await repository.list_resource_records(resource_id=first.resource_id) == before
