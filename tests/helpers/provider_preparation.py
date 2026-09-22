"""Layer: contract support. Explicit admission fixture for isolated transport tests."""
from orket.application.services.local_model_factory import (
    create_local_model_provider,
    create_local_model_provider_async,
)
from orket.core.contracts.provider_runtime import ProviderRuntimeTarget, normalize_provider


class ControlledPreparation:
    async def prepare(self, request):
        return ProviderRuntimeTarget(
            requested_provider=request.provider, canonical_provider=normalize_provider(request.provider),
            requested_model=request.requested_model, model_id=request.requested_model, base_url=request.base_url,
            resolution_mode="controlled_test_admission", inventory_source="test_fixture",
            available_models=(request.requested_model,), loaded_models_before=(), loaded_models_after=(),
            auto_load_attempted=False, auto_load_performed=False, status="OK",
        )


def create_test_model_provider(*args, **kwargs):
    """Keep real factory/prompt/transport behavior; explicitly supply controlled admission."""
    return create_local_model_provider(*args, runtime_preparation=ControlledPreparation(), **kwargs)


async def create_test_model_provider_async(*args, **kwargs):
    """Use owned construction with the same explicit controlled admission."""
    return await create_local_model_provider_async(*args, runtime_preparation=ControlledPreparation(), **kwargs)
