import types

import orket.hardware as hardware


def test_metrics_snapshot_uses_vram_cache(monkeypatch):
    calls = {"count": 0}

    def fake_vram_info():
        calls["count"] += 1
        return 12.0

    def fake_vram_usage():
        calls["count"] += 1
        return 4.0

    monkeypatch.setenv("ORKET_METRICS_VRAM_CACHE_SEC", "60")
    monkeypatch.setattr(hardware, "get_vram_info", fake_vram_info)
    monkeypatch.setattr(hardware, "get_vram_usage", fake_vram_usage)
    monkeypatch.setattr(hardware.psutil, "virtual_memory", lambda: types.SimpleNamespace(percent=42.0))
    monkeypatch.setattr(hardware.psutil, "cpu_percent", lambda interval=None: 11.0)
    monkeypatch.setattr(hardware, "_VRAM_CACHE", {"ts": 0.0, "total": 0.0, "used": 0.0})

    # First call warms cache; second call should not re-query VRAM subprocess paths.
    first = hardware.get_metrics_snapshot()
    second = hardware.get_metrics_snapshot()

    assert first["vram_total_gb"] == 12.0
    assert first["vram_gb_used"] == 4.0
    assert second["vram_total_gb"] == 12.0
    assert second["vram_gb_used"] == 4.0
    assert calls["count"] == 2


def test_metrics_snapshot_invalid_cache_ttl_falls_back(monkeypatch):
    monkeypatch.setenv("ORKET_METRICS_VRAM_CACHE_SEC", "not-a-number")
    monkeypatch.setattr(hardware.psutil, "virtual_memory", lambda: types.SimpleNamespace(percent=10.0))
    monkeypatch.setattr(hardware.psutil, "cpu_percent", lambda interval=None: 5.0)
    monkeypatch.setattr(hardware, "get_vram_info", lambda: 0.0)
    monkeypatch.setattr(hardware, "get_vram_usage", lambda: 0.0)
    monkeypatch.setattr(hardware, "_VRAM_CACHE", {"ts": 0.0, "total": 0.0, "used": 0.0})

    snapshot = hardware.get_metrics_snapshot()
    assert snapshot["vram_total_gb"] == 0.0
    assert snapshot["vram_gb_used"] == 0.0
