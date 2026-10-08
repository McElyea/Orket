"""Native host observation through the API application worker boundary."""
import asyncio
import platform

import psutil
import pytest

from orket.application.services.api_system_query_service import ApiSystemQueryService
from orket.application.services.runtime_input_service import RuntimeInputService

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_application_observes_native_host_memory(tmp_path):
    service = ApiSystemQueryService(tmp_path, environment={}, runtime_inputs=RuntimeInputService())
    snapshot = await service.hardware_metrics()
    assert 0 <= snapshot["cpu_percent"] <= 100
    assert 0 <= snapshot["ram_percent"] <= 100
    host = await asyncio.to_thread(platform.uname)
    assert snapshot["architecture"] == host.machine
    if host.system == "Darwin" and host.machine.lower() in {"arm64", "aarch64"}:
        memory = await asyncio.to_thread(psutil.virtual_memory)
        assert snapshot["unified_memory_gb"] == memory.total / 1024**3
        assert snapshot["vram_total_gb"] is None
        assert snapshot["gpu_observation"] == "metal_unverified"
    else:
        assert snapshot["memory_model"] in {"dedicated", "unknown"}
        assert snapshot["gpu_observation"] in {"nvidia_observed", "unobserved"}
