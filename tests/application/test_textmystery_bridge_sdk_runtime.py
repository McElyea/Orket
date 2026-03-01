from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from orket.extensions import ExtensionManager


def _load_register_module():
    script_path = Path("scripts/register_textmystery_bridge_extension.py").resolve()
    spec = importlib.util.spec_from_file_location("register_textmystery_bridge_extension_runtime", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load register_textmystery_bridge_extension.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _init_fake_textmystery_root(root: Path) -> None:
    src = root / "src" / "textmystery" / "interfaces"
    src.mkdir(parents=True, exist_ok=True)
    (src.parent / "__init__.py").write_text("", encoding="utf-8")
    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "live_contract.py").write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "def parity_check(request_payload: dict[str, object]) -> dict[str, object]:",
                "    turns = request_payload.get('transcript_inputs') if isinstance(request_payload.get('transcript_inputs'), list) else []",
                "    return {",
                "        'world_digest': 'fake-world-digest-v1',",
                "        'turn_results': [{'turn': int(i + 1), 'decision': 'ANSWER'} for i, _ in enumerate(turns)],",
                "        'accusation_result': {'accused_npc_id': 'VICTOR_SLATE', 'outcome': 'LOSE', 'reveal_digest': 'fake-reveal'}",
                "    }",
                "",
                "def leak_check(request_payload: dict[str, object]) -> dict[str, object]:",
                "    return {'ok': True, 'violations': []}",
            ]
        ),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_textmystery_bridge_sdk_workload_deterministic_with_local_contract(tmp_path, monkeypatch):
    fake_textmystery = tmp_path / "fake_textmystery"
    _init_fake_textmystery_root(fake_textmystery)

    register_module = _load_register_module()
    monkeypatch.setattr(register_module, "PROJECT_ROOT", tmp_path)
    durable_root = tmp_path / ".orket_durable"
    monkeypatch.setenv("ORKET_DURABLE_ROOT", str(durable_root))
    assert register_module.main() == 0

    manager = ExtensionManager(project_root=tmp_path)
    workspace = tmp_path / "workspace" / "default"
    workspace.mkdir(parents=True, exist_ok=True)
    input_config = {
        "operation": "parity-check",
        "textmystery_root": str(fake_textmystery),
        "payload": {"transcript_inputs": [{"turn": 1, "npc_id": "NICK_VALE", "raw_question": "Where?"}]},
    }
    first = await manager.run_workload(
        workload_id="textmystery_bridge_v1",
        input_config=input_config,
        workspace=workspace,
        department="core",
    )
    second = await manager.run_workload(
        workload_id="textmystery_bridge_v1",
        input_config=input_config,
        workspace=workspace,
        department="core",
    )

    assert first.summary["output"] == second.summary["output"]
    assert first.plan_hash == second.plan_hash
    assert Path(first.provenance_path).exists()
    assert Path(second.provenance_path).exists()
    assert (Path(first.artifact_root) / "bridge_response.json").exists()
    assert (Path(first.artifact_root) / "turn_results.json").exists()
    assert (Path(first.artifact_root) / "bridge_tts_clip.pcm").exists()
    assert first.summary["output"]["audio"]["format"] == "pcm_s16le"
