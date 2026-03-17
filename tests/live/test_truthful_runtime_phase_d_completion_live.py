from __future__ import annotations

from pathlib import Path

import pytest

from orket.application.services.companion_runtime_service import CompanionRuntimeService
from orket.capabilities.sdk_memory_provider import SQLiteMemoryCapabilityProvider
from orket.runtime.truthful_memory_policy import render_reference_context_rows
from orket.services.memory_store import MemoryStore
from orket.services.scoped_memory_store import ScopedMemoryStore
from orket_extension_sdk.memory import MemoryQueryRequest, MemoryWriteRequest
from tests.live.test_runtime_stability_closeout_live import _live_enabled

pytestmark = pytest.mark.end_to_end


def test_phase_d_live_durable_memory_requires_explicit_user_correction(tmp_path: Path) -> None:
    """Layer: end-to-end. Verifies the real SQLite memory provider blocks contradicting durable-fact writes until user correction is explicit."""
    if not _live_enabled():
        pytest.skip("Set ORKET_LIVE_ACCEPTANCE=1 to run live Phase D proof.")

    provider = SQLiteMemoryCapabilityProvider(tmp_path / "phase_d_live_memory.db")
    initial = provider.write(
        MemoryWriteRequest(
            scope="profile_memory",
            key="user_fact.name",
            value="Aster",
            metadata={"user_confirmed": True, "observed_at": "2026-03-17T14:00:00+00:00"},
        )
    )
    blocked = provider.write(
        MemoryWriteRequest(
            scope="profile_memory",
            key="user_fact.name",
            value="Nova",
            metadata={"user_confirmed": True, "observed_at": "2026-03-17T14:05:00+00:00"},
        )
    )
    corrected = provider.write(
        MemoryWriteRequest(
            scope="profile_memory",
            key="user_fact.name",
            value="Nova",
            metadata={
                "user_confirmed": True,
                "user_correction": True,
                "write_rationale": "user corrected the stored name",
                "observed_at": "2026-03-17T14:06:00+00:00",
            },
        )
    )
    exact = provider.query(MemoryQueryRequest(scope="profile_memory", query="key:user_fact.name", limit=10))

    assert initial.ok is True
    assert blocked.ok is False
    assert corrected.ok is True
    assert exact.ok is True
    record = exact.records[0]
    print(
        "[live][phase-d][durable-correction] "
        f"path=primary result=success conflict={record.metadata['conflict_resolution']} "
        f"trust={record.metadata['trust_level']}"
    )
    assert blocked.error_code == "E_PROFILE_MEMORY_CONTRADICTION_REQUIRES_CORRECTION"
    assert record.value == "Nova"
    assert record.metadata["conflict_resolution"] == "user_correction"
    assert record.metadata["trust_level"] == "authoritative"


@pytest.mark.asyncio
async def test_phase_d_live_companion_governed_memory_context_filters_stale_rows(tmp_path: Path) -> None:
    """Layer: end-to-end. Verifies the real companion runtime synthesizes only governed-trust memory rows into context."""
    if not _live_enabled():
        pytest.skip("Set ORKET_LIVE_ACCEPTANCE=1 to run live Phase D proof.")

    store = ScopedMemoryStore(tmp_path / "phase_d_live_companion.db")
    await store.write_profile(
        key="companion_setting.role_id",
        value="strategist",
        metadata={"observed_at": "2026-03-17T14:00:00+00:00"},
    )
    await store.write_episodic(
        session_id="phase-d-live",
        key="turn.000001.summary",
        value="Fresh summary",
        metadata={"kind": "episodic_turn"},
    )
    await store.write_episodic(
        session_id="phase-d-live",
        key="turn.000000.summary",
        value="Stale summary",
        metadata={"kind": "episodic_turn", "stale_at": "2000-01-01T00:00:00+00:00"},
    )

    service = CompanionRuntimeService(project_root=tmp_path, memory_store=store)
    await service.update_config(
        session_id="phase-d-live",
        scope="session",
        patch={"memory": {"episodic_memory_enabled": True}},
    )
    config = await service.get_config(session_id="phase-d-live")
    context = await service._build_memory_context(session_id="phase-d-live", config=config)

    print(
        "[live][phase-d][companion-context] "
        f"path=primary result=success lines={len([line for line in context.splitlines() if line.strip()])}"
    )
    assert "[profile][trust=authoritative] companion_setting.role_id: strategist" in context
    assert "[episodic][trust=advisory] turn.000001.summary: Fresh summary" in context
    assert "Stale summary" not in context


@pytest.mark.asyncio
async def test_phase_d_live_reference_context_rendering_filters_stale_project_memory(tmp_path: Path) -> None:
    """Layer: end-to-end. Verifies the real project-memory reference context renderer excludes stale rows and labels included trust."""
    if not _live_enabled():
        pytest.skip("Set ORKET_LIVE_ACCEPTANCE=1 to run live Phase D proof.")

    store = MemoryStore(tmp_path / "phase_d_live_project_memory.db")
    await store.remember("Fresh decision note", {"type": "decision"})
    await store.remember("Stale decision note", {"type": "decision", "stale_at": "2000-01-01T00:00:00+00:00"})

    results = await store.search("decision", limit=10)
    rendered = render_reference_context_rows(results)

    print(
        "[live][phase-d][reference-context] "
        f"path=primary result=success rendered_lines={len([line for line in rendered.splitlines() if line.strip()])}"
    )
    assert "[reference_context][trust=advisory] Fresh decision note" in rendered
    assert "Stale decision note" not in rendered
