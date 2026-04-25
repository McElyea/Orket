from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.extensions.manager import ExtensionManager

HOST_CONTROLS_KEY = "__orket_host_capability_authorization__"
OUTPUT_PATH = REPO_ROOT / "benchmarks" / "results" / "extensions" / "extension_capability_audit.json"
PROOF_REF = "python scripts/extensions/build_extension_capability_audit.py --strict"
MEMORY_QUERY_SOURCE = "\n".join(
    [
        "from __future__ import annotations",
        "from orket_extension_sdk import WorkloadResult",
        "from orket_extension_sdk.memory import MemoryQueryRequest",
        "",
        "def run_workload(ctx, payload):",
        "    response = ctx.capabilities.memory_query().query(",
        "        MemoryQueryRequest(scope='profile_memory', query='', limit=5)",
        "    )",
        "    return WorkloadResult(ok=response.ok, output={'record_count': len(response.records)})",
    ]
)
MEMORY_WRITE_SOURCE = "\n".join(
    [
        "from __future__ import annotations",
        "from orket_extension_sdk import WorkloadResult",
        "from orket_extension_sdk.memory import MemoryWriteRequest",
        "",
        "def run_workload(ctx, payload):",
        "    response = ctx.capabilities.memory_writer().write(",
        "        MemoryWriteRequest(scope='profile_memory', key='companion_setting.role_id', value='planner')",
        "    )",
        "    return WorkloadResult(ok=response.ok, output={'key': response.key})",
    ]
)
MODEL_GENERATE_SOURCE = "\n".join(
    [
        "from __future__ import annotations",
        "from orket_extension_sdk import WorkloadResult",
        "from orket_extension_sdk.llm import GenerateRequest",
        "",
        "def run_workload(ctx, payload):",
        "    response = ctx.capabilities.llm().generate(",
        "        GenerateRequest(system_prompt='system', user_message='hello world')",
        "    )",
        "    return WorkloadResult(ok=True, output={'text': response.text, 'model': response.model})",
    ]
)
VOICE_FAMILY_SOURCE = "\n".join(
    [
        "from __future__ import annotations",
        "from orket_extension_sdk import WorkloadResult",
        "from orket_extension_sdk.audio import AudioClip",
        "from orket_extension_sdk.voice import TranscribeRequest, VoiceTurnControlRequest",
        "",
        "def run_workload(ctx, payload):",
        "    transcribed = ctx.capabilities.stt().transcribe(TranscribeRequest(audio_bytes=b''))",
        "    clip = ctx.capabilities.tts().synthesize('hello there', voice_id='null')",
        "    ctx.capabilities.audio_player().play(clip, blocking=False)",
        "    ctx.capabilities.speech_player().play(",
        "        AudioClip(sample_rate=22050, channels=1, samples=b'\\x00\\x01', format='pcm_s16le'),",
        "        blocking=False,",
        "    )",
        "    turn = ctx.capabilities.voice_turn_controller().control(VoiceTurnControlRequest(command='start'))",
        "    return WorkloadResult(",
        "        ok=True,",
        "        output={",
        "            'stt_ok': transcribed.ok,",
        "            'transcribe_error_code': transcribed.error_code or '',",
        "            'turn_state': turn.state,",
        "            'clip_format': clip.format,",
        "        },",
        "    )",
    ]
)
TTS_SPEAK_SOURCE = "\n".join(
    [
        "from __future__ import annotations",
        "from orket_extension_sdk import WorkloadResult",
        "",
        "def run_workload(ctx, payload):",
        "    clip = ctx.capabilities.tts().synthesize('blocked proof', voice_id='null')",
        "    return WorkloadResult(ok=True, output={'clip_format': clip.format})",
    ]
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate the canonical SDK capability authorization audit artifact.")
    parser.add_argument("--out", default=str(OUTPUT_PATH), help="Stable output JSON path.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when observed rows drift from expected results.")
    return parser


def _init_sdk_repo(repo_root: Path, *, module_source: str, required_capabilities: list[str]) -> None:
    (repo_root / "extension.yaml").write_text(
        "\n".join(
            [
                "manifest_version: v0",
                "extension_id: sdk.audit.extension",
                "extension_version: 0.1.0",
                "allowed_stdlib_modules:",
                "  - pathlib",
                "workloads:",
                "  - workload_id: sdk_audit_v1",
                "    entrypoint: sdk_audit_extension:run_workload",
                f"    required_capabilities: {json.dumps(required_capabilities)}",
            ]
        ),
        encoding="utf-8",
    )
    (repo_root / "sdk_audit_extension.py").write_text(module_source, encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "init"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )


def _controls(*, test_case: str, expected_result: str, admit_only: list[str] | None = None, child_extra_capabilities: list[str] | None = None) -> dict[str, Any]:
    return {
        HOST_CONTROLS_KEY: {
            "admit_only": list(admit_only or []),
            "child_extra_capabilities": list(child_extra_capabilities or []),
            "audit_case": {"test_case": test_case, "expected_result": expected_result, "proof_ref": PROOF_REF},
        }
    }


async def _run_case(project_root: Path, case: dict[str, Any]) -> None:
    repo = project_root / "repos" / str(case["test_case"])
    repo.mkdir(parents=True, exist_ok=True)
    _init_sdk_repo(repo, module_source=str(case["module_source"]), required_capabilities=list(case["required_capabilities"]))
    manager = ExtensionManager(catalog_path=project_root / "extensions_catalog.json", project_root=project_root)
    manager.install_from_repo(str(repo))
    workspace = project_root / "workspace" / "default"
    input_config = dict(case["input_config"])
    if "capabilities" in case:
        input_config["capabilities"] = dict(case["capabilities"])
    try:
        await manager.run_workload(
            workload_id="sdk_audit_v1",
            input_config=input_config,
            workspace=workspace,
            department="core",
        )
    except RuntimeError:
        if str(case["expected_result"]) != "blocked":
            raise


def _collect_rows(
    project_root: Path,
    *,
    expected_results_by_test_case: dict[str, str],
    expected_call_results_by_test_case: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for provenance_path in sorted((project_root / "workspace" / "extensions").rglob("provenance.json")):
        payload = json.loads(provenance_path.read_text(encoding="utf-8"))
        auth = payload.get("sdk_capability_authorization")
        if not isinstance(auth, dict):
            continue
        audit_case = dict(auth.get("audit_case") or {})
        test_case = str(audit_case.get("test_case") or "")
        expected_call_results = expected_call_results_by_test_case.get(test_case, {})
        for call_record in list(auth.get("call_records") or []):
            if not isinstance(call_record, dict):
                continue
            capability_id = str(call_record.get("capability_id") or "")
            rows.append(
                {
                    "test_case": test_case,
                    "extension_id": payload["extension"]["extension_id"],
                    "workload_id": payload["workload"]["workload_id"],
                    "authorization_surface": auth.get("authorization_surface", "host_authorized_capability_registry_v1"),
                    "declared_capabilities": list(auth.get("declared_capabilities") or []),
                    "admitted_capabilities": list(auth.get("admitted_capabilities") or []),
                    "instantiated_capabilities": list(auth.get("instantiated_capabilities") or []),
                    "used_capabilities": list(auth.get("used_capabilities") or []),
                    "authorization_basis": auth.get("authorization_basis", ""),
                    "policy_version": auth.get("policy_version", ""),
                    "authorization_digest": auth.get("authorization_digest", ""),
                    "expected_result": expected_call_results.get(
                        capability_id,
                        expected_results_by_test_case.get(test_case, str(audit_case.get("expected_result") or "")),
                    ),
                    "observed_result": str(call_record.get("observed_result") or ""),
                    "denial_class": str(call_record.get("denial_class") or ""),
                    "proof_ref": str(audit_case.get("proof_ref") or PROOF_REF),
                }
            )
    return rows


def _build_cases() -> list[dict[str, Any]]:
    return [
        {
            "test_case": "memory_query_allowed",
            "expected_result": "success",
            "module_source": MEMORY_QUERY_SOURCE,
            "required_capabilities": ["memory.query", "memory.write"],
            "input_config": _controls(test_case="memory_query_allowed", expected_result="success", admit_only=["memory.query"]),
        },
        {
            "test_case": "memory_write_allowed",
            "expected_result": "success",
            "module_source": MEMORY_WRITE_SOURCE,
            "required_capabilities": ["memory.query", "memory.write"],
            "input_config": _controls(test_case="memory_write_allowed", expected_result="success", admit_only=["memory.write"]),
        },
        {
            "test_case": "memory_write_undeclared",
            "expected_result": "blocked",
            "module_source": MEMORY_WRITE_SOURCE,
            "required_capabilities": [],
            "input_config": _controls(test_case="memory_write_undeclared", expected_result="blocked"),
        },
        {
            "test_case": "memory_write_denied",
            "expected_result": "blocked",
            "module_source": MEMORY_WRITE_SOURCE,
            "required_capabilities": ["memory.query", "memory.write"],
            "input_config": _controls(test_case="memory_write_denied", expected_result="blocked", admit_only=["memory.query"]),
        },
        {
            "test_case": "child_drift_memory_write",
            "expected_result": "blocked",
            "module_source": MEMORY_QUERY_SOURCE,
            "required_capabilities": ["memory.query"],
            "input_config": _controls(
                test_case="child_drift_memory_write",
                expected_result="blocked",
                admit_only=["memory.query"],
                child_extra_capabilities=["memory.write"],
            ),
        },
        {
            "test_case": "model_generate_allowed",
            "expected_result": "success",
            "module_source": MODEL_GENERATE_SOURCE,
            "required_capabilities": ["model.generate"],
            "input_config": _controls(test_case="model_generate_allowed", expected_result="success", admit_only=["model.generate"]),
            "capabilities": {"model.generate": {"provider": "static_llm", "text": "static capability proof", "model": "static-model"}},
        },
        {
            "test_case": "voice_families_governed",
            "expected_result": "mixed",
            "module_source": VOICE_FAMILY_SOURCE,
            "required_capabilities": [
                "speech.transcribe",
                "tts.speak",
                "audio.play",
                "speech.play_clip",
                "voice.turn_control",
            ],
            "input_config": _controls(
                test_case="voice_families_governed",
                expected_result="mixed",
                admit_only=[
                    "speech.transcribe",
                    "tts.speak",
                    "audio.play",
                    "speech.play_clip",
                    "voice.turn_control",
                ],
            ),
            "expected_call_results": {
                "speech.transcribe": "failure",
                "tts.speak": "success",
                "audio.play": "success",
                "speech.play_clip": "success",
                "voice.turn_control": "success",
            },
        },
        {
            "test_case": "tts_speak_denied",
            "expected_result": "blocked",
            "module_source": TTS_SPEAK_SOURCE,
            "required_capabilities": ["tts.speak", "memory.query"],
            "input_config": _controls(
                test_case="tts_speak_denied",
                expected_result="blocked",
                admit_only=["memory.query"],
            ),
        },
    ]


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    cases = _build_cases()
    with tempfile.TemporaryDirectory(prefix="orket-extension-capability-audit-") as temp_dir:
        project_root = Path(temp_dir).resolve()
        for case in cases:
            asyncio.run(_run_case(project_root, case))
        rows = _collect_rows(
            project_root,
            expected_results_by_test_case={
                str(case["test_case"]): str(case["expected_result"])
                for case in cases
            },
            expected_call_results_by_test_case={
                str(case["test_case"]): dict(case.get("expected_call_results") or {})
                for case in cases
            },
        )
    payload = {
        "schema_version": "extension_capability_audit.v1",
        "authorization_surface": "host_authorized_capability_registry_v1",
        "rows": rows,
    }
    persisted = write_payload_with_diff_ledger(Path(str(args.out)).resolve(), payload)
    if bool(args.strict):
        expected_cases = {case["test_case"] for case in cases}
        observed_cases = {row["test_case"] for row in rows}
        if expected_cases != observed_cases:
            return 1
        if any(row["expected_result"] != row["observed_result"] for row in rows):
            return 1
    print(json.dumps(persisted, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
