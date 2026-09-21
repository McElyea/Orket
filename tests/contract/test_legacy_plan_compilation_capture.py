"""A workload's later material callback cannot rewrite its admitted action plan."""
from types import SimpleNamespace

import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.extensions.contracts import RunAction, RunPlan
from orket.extensions.models import _ExtensionManifestEntry
from orket.extensions.reproducibility import ReproducibilityEnforcer
from orket.extensions.workload_artifacts import WorkloadArtifacts
from orket.extensions.workload_policy import capture_workload_policy
from orket.extensions.workload_publication import prepare_legacy_workload

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


async def test_material_callback_cannot_rewrite_compiled_legacy_actions(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_RELIABLE_MODE", "true")
    monkeypatch.setenv("ORKET_RELIABLE_REQUIRE_CLEAN_GIT", "false")
    params, metadata = {"session_id": "admitted"}, {"marker": "admitted"}
    raw_plan = RunPlan("capture", "1", (RunAction("run_card", "card", params),), metadata)
    admitted_hash = raw_plan.plan_hash()

    def materials():
        params["session_id"] = "replaced"
        metadata["marker"] = "replaced"
        return []

    workload = SimpleNamespace(compile=lambda _: raw_plan, required_materials=materials)
    loader = SimpleNamespace(load_legacy_workload=lambda *_: workload)
    artifacts = await run_owned_thread(lambda: WorkloadArtifacts(tmp_path, ReproducibilityEnforcer(tmp_path)),
                                       label="legacy-material-contract-construction")
    loaded, admitted = await prepare_legacy_workload(loader, artifacts, None, _ExtensionManifestEntry("capture", "1"),
                                                    {}, None, policy=capture_workload_policy())
    assert loaded is workload and raw_plan.plan_hash() != admitted_hash
    assert admitted.plan_hash() == admitted_hash and admitted.actions[0].params == {"session_id": "admitted"}
