"""Controlled platform facts test reporting semantics, not native Metal behavior."""
from types import SimpleNamespace

import pytest

from orket import hardware
from orket.interfaces.operator_view_support import build_system_health_view

pytestmark = pytest.mark.contract


def test_apple_memory_is_not_nvidia_vram_or_proof_of_model_fit(monkeypatch):
    monkeypatch.setattr(hardware.platform, "uname", lambda: SimpleNamespace(system="Darwin", machine="arm64"))
    monkeypatch.setattr(hardware.psutil, "virtual_memory",
                        lambda: SimpleNamespace(total=64 * 1024**3, percent=25.0))
    monkeypatch.setattr(hardware.psutil, "cpu_count", lambda **_kwargs: 8)
    monkeypatch.setattr(hardware.psutil, "cpu_percent", lambda **_kwargs: 3.0)

    def forbidden_probe():
        pytest.fail("Apple observations must not invoke NVIDIA discovery")

    monkeypatch.setattr(hardware, "get_vram_info", forbidden_probe)
    monkeypatch.setattr(hardware, "get_vram_usage", forbidden_probe)
    profile = hardware.get_current_profile()
    assert (profile.ram_gb, profile.vram_gb, profile.has_nvidia) == (64.0, None, False)
    assert profile.memory_model == "unified"
    assert profile.gpu_observation == "metal_unverified"
    assert hardware.can_handle_model_tier(hardware.ModelTier.T1_MINI, profile) is None
    assert hardware.can_handle_model_tier(hardware.ModelTier.T5_ULTRA, profile) is None
    assert hardware.can_handle_tier(hardware.ToolTier.TIER_2_VISION, profile) is False
    metrics = hardware.get_metrics_snapshot()
    view = build_system_health_view(heartbeat={"status": "online"}, metrics=metrics, provider_status={})
    for values in (metrics, view):
        assert values["vram_total_gb"] is None
        assert values["vram_gb_used"] is None
        assert values["unified_memory_gb"] == 64.0
        assert values["gpu_observation"] == "metal_unverified"
        assert values["memory_model"] == "unified"
    assert "system.vram_hot" not in view["reason_codes"]


@pytest.mark.asyncio
async def test_hardware_observation_refuses_event_loop_before_native_probe(monkeypatch):
    def forbidden_probe():
        pytest.fail("Native probe ran on event-loop thread")

    monkeypatch.setattr(hardware.platform, "uname", forbidden_probe)
    for observe in (hardware.get_current_profile, hardware.get_metrics_snapshot,
                    hardware.get_vram_info, hardware.get_vram_usage):
        with pytest.raises(RuntimeError, match="E_HARDWARE_REQUIRES_NATIVE_OWNER"):
            observe()
