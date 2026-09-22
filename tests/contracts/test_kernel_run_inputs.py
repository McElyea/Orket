"""Layer: contract. Immutable run values and pure handle construction."""

from dataclasses import FrozenInstanceError

import pytest

from orket.core.contracts.kernel_run_inputs import KernelRunInputs, KernelWorkspaceInputs
from orket.kernel.v1.api import start_run

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("identity", [None, "", 1, True, [], {}])
def test_selected_identity_must_be_a_nonempty_plain_string(tmp_path, identity):
    with pytest.raises(ValueError, match="E_KERNEL_RUN_ID_NONEMPTY_STRING_REQUIRED"):
        KernelRunInputs(identity, KernelWorkspaceInputs(str(tmp_path)))


@pytest.mark.parametrize("root", [None, "", "relative", 1, True])
def test_workspace_is_an_explicit_absolute_string(root):
    with pytest.raises(ValueError, match="E_KERNEL_WORKSPACE_ABSOLUTE_STRING_REQUIRED"):
        KernelWorkspaceInputs(root)


@pytest.mark.asyncio
async def test_typed_start_is_pure_repeatable_and_owned(tmp_path, monkeypatch):
    import orket.application.services.kernel_invocation_inputs as context
    import orket.application.services.runtime_input_service as source

    def unexpected():
        raise AssertionError("typed start reached an ambient input")

    monkeypatch.setattr(source, "uuid4", unexpected)
    monkeypatch.setattr(context, "default_project_root", unexpected)
    inputs = KernelRunInputs("explicit-run", KernelWorkspaceInputs(str(tmp_path / "absent")))
    request = {"contract_version": "kernel_api/v1", "workflow_id": "pure", "workspace_root": "ignored"}
    expected = {
        "contract_version": "kernel_api/v1",
        "run_handle": {
            "contract_version": "kernel_api/v1",
            "run_id": "explicit-run",
            "visibility_mode": "local_only",
            "workspace_root": str(tmp_path / "absent"),
        },
    }
    first = start_run(request, run_inputs=inputs)
    assert first == expected == start_run(request, run_inputs=inputs)
    first["run_handle"]["run_id"] = "changed"
    assert start_run(request, run_inputs=inputs) == expected
    with pytest.raises(FrozenInstanceError):
        inputs.run_id = "changed"
    with pytest.raises(FrozenInstanceError):
        inputs.workspace.root = "changed"
    assert not (tmp_path / "absent").exists()
    with pytest.raises(TypeError, match="E_KERNEL_RUN_INPUTS_REQUIRED"):
        start_run(request, run_inputs={"run_id": "wire"})


def test_core_run_value_refuses_untyped_workspace():
    with pytest.raises(TypeError, match="E_KERNEL_WORKSPACE_INPUTS_REQUIRED"):
        KernelRunInputs("run-typed", {"root": "borrowed"})
