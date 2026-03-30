from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import orket.extensions as extensions_package
import orket.extensions.manager as extension_manager_module
import orket.extensions.models as extension_models
from orket.capabilities.sdk_voice_provider import HostSTTCapabilityProvider, HostVoiceTurnController
from orket.capabilities.sdk_memory_provider import SQLiteMemoryCapabilityProvider
from orket_extension_sdk.audio import NullAudioPlayer, NullTTSProvider
from orket_extension_sdk.llm import LLMProvider
from orket_extension_sdk.memory import MemoryWriteRequest
from orket_extension_sdk.result import ArtifactRef, WorkloadResult

from orket.application.services.control_plane_workload_catalog import (
    WorkloadAuthorityInput,
    resolve_control_plane_workload,
)
from orket.extensions.catalog import ExtensionCatalog
from orket.extensions.manifest_parser import ManifestParser
from orket.extensions.models import CONTRACT_STYLE_LEGACY
from orket.extensions.reproducibility import ReproducibilityEnforcer
from orket.extensions.runtime import ExtensionEngineAdapter, RunContext
from orket.extensions.contracts import RunAction
from orket.extensions.workload_artifacts import WorkloadArtifacts
from orket.extensions.workload_executor import WorkloadExecutor
from orket.extensions.workload_loader import WorkloadLoader
from orket.extensions.contracts import RunPlan
from orket.extensions.governed_identity import build_governed_identity


def test_extension_catalog_load_and_list(tmp_path: Path) -> None:
    """Layer: unit. Verifies installed extension catalog rows use manifest-entry storage."""
    catalog_path = tmp_path / "catalog.json"
    payload = {
        "extensions": [
            {
                "extension_id": "demo.ext",
                "extension_version": "1.2.3",
                "source": "git+demo",
                "manifest_entries": [{"workload_id": "demo_v1", "workload_version": "1.0.0"}],
            }
        ]
    }
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")

    catalog = ExtensionCatalog(catalog_path)
    records = catalog.list_extensions()

    assert len(records) == 1
    assert records[0].extension_id == "demo.ext"
    assert records[0].manifest_entries[0].workload_id == "demo_v1"


def test_extension_catalog_load_and_list_supports_legacy_workloads_key(tmp_path: Path) -> None:
    """Layer: unit. Verifies installed catalog reads remain backward-compatible with legacy workload rows."""
    catalog_path = tmp_path / "catalog.json"
    payload = {
        "extensions": [
            {
                "extension_id": "demo.ext",
                "extension_version": "1.2.3",
                "source": "git+demo",
                "workloads": [{"workload_id": "demo_v1", "workload_version": "1.0.0"}],
            }
        ]
    }
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")

    catalog = ExtensionCatalog(catalog_path)
    records = catalog.list_extensions()

    assert len(records) == 1
    assert records[0].extension_id == "demo.ext"
    assert records[0].manifest_entries[0].workload_id == "demo_v1"


def test_extension_catalog_workload_projects_into_control_plane_workload_record(tmp_path: Path) -> None:
    """Layer: unit. Verifies persisted extension catalog manifest entries still resolve canonical workload authority."""
    catalog_path = tmp_path / "catalog.json"
    payload = {
        "extensions": [
            {
                "extension_id": "demo.ext",
                "extension_version": "1.2.3",
                "source": "git+demo",
                "manifest_digest_sha256": "f" * 64,
                "manifest_entries": [
                    {
                        "workload_id": "demo_v1",
                        "workload_version": "1.0.0",
                        "entrypoint": "demo:run",
                        "required_capabilities": ["workspace.root"],
                        "contract_style": "sdk_v0",
                    }
                ],
            }
        ]
    }
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")

    catalog = ExtensionCatalog(catalog_path)
    extension = catalog.list_extensions()[0]
    workload = extension.manifest_entries[0]
    record = resolve_control_plane_workload(
        WorkloadAuthorityInput(
            kind="extension_manifest_workload",
            workload_id=workload.workload_id,
            workload_version=workload.workload_version,
            extension_id=extension.extension_id,
            extension_version=extension.extension_version,
            entrypoint=workload.entrypoint,
            required_capabilities=workload.required_capabilities,
            contract_style=workload.contract_style or extension.contract_style,
            manifest_digest_sha256=extension.manifest_digest_sha256,
        )
    )

    assert record.workload_id == "demo_v1"
    assert record.input_contract_ref == "extension_manifest:sdk_v0"
    assert record.output_contract_ref == "extension_run_result_identity_v1"
    assert record.workload_digest.startswith("sha256:")


def test_manifest_parser_load_manifest_legacy(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "orket_extension.json").write_text(
        json.dumps(
            {
                "extension_id": "demo.ext",
                "extension_version": "0.1.0",
                "module": "demo_module",
                "workloads": [{"workload_id": "demo_v1", "workload_version": "0.1.0"}],
            }
        ),
        encoding="utf-8",
    )

    parser = ManifestParser()
    loaded = parser.load_manifest(repo)

    assert loaded.contract_style == CONTRACT_STYLE_LEGACY
    record = parser.record_from_manifest(
        loaded.payload,
        source="demo",
        path=repo,
        contract_style=loaded.contract_style,
        manifest_path=loaded.manifest_path,
    )
    assert record.extension_id == "demo.ext"


def test_reproducibility_enforcer_reliable_mode_enabled_default(tmp_path: Path) -> None:
    enforcer = ReproducibilityEnforcer(tmp_path)
    assert enforcer.reliable_mode_enabled() is True


def test_workload_loader_parse_sdk_entrypoint() -> None:
    loader = WorkloadLoader(registry_factory=lambda: None)  # type: ignore[arg-type]
    module_name, attr_name = loader.parse_sdk_entrypoint("demo.module:run")
    assert module_name == "demo.module"
    assert attr_name == "run"


def test_workload_artifacts_build_manifest(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir(parents=True)
    (artifact_root / "a.txt").write_text("hello", encoding="utf-8")

    artifacts = WorkloadArtifacts(tmp_path, ReproducibilityEnforcer(tmp_path))
    governed_identity = build_governed_identity(
        operator_surface="extension_run_result_identity_v1",
        policy_payload={"policy_surface_version": "test.v1"},
        control_bundle={"input_identity": "plan-123"},
    )
    manifest = artifacts.build_artifact_manifest(
        artifact_root,
        plan_hash="plan-123",
        governed_identity=governed_identity,
    )

    assert manifest["files"][0]["path"] == "a.txt"
    assert len(manifest["manifest_sha256"]) == 64
    assert manifest["claim_tier"] == "non_deterministic_lab_only"
    assert manifest["compare_scope"] == "extension_workload_provenance_family_v1"
    assert manifest["operator_surface"] == "extension_artifact_manifest_v1"
    assert manifest["policy_digest"].startswith("sha256:")
    assert manifest["control_bundle_hash"].startswith("sha256:")
    assert manifest["plan_hash"] == "plan-123"
    assert manifest["provenance_ref"] == "provenance.json"
    assert manifest["determinism_class"] == "workspace"


def test_workload_artifacts_validate_sdk_artifacts_rejects_prefix_escape(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir(parents=True)
    outside_dir = tmp_path / "artifacts-evil"
    outside_dir.mkdir(parents=True)
    outside_file = outside_dir / "outside.txt"
    outside_file.write_text("not-inside-root", encoding="utf-8")

    digest = hashlib.sha256(outside_file.read_bytes()).hexdigest()
    result = WorkloadResult(
        ok=True,
        artifacts=[ArtifactRef(path="../artifacts-evil/outside.txt", digest_sha256=digest, kind="text")],
    )

    artifacts = WorkloadArtifacts(tmp_path, ReproducibilityEnforcer(tmp_path))
    with pytest.raises(ValueError, match="E_ARTIFACT_PATH_TRAVERSAL"):
        artifacts.validate_sdk_artifacts(result, artifact_root)


def test_workload_artifacts_rejects_symlink_in_sdk_validation_and_manifest(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir(parents=True)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    link_path = artifact_root / "linked.txt"
    try:
        link_path.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlink unsupported in this environment: {exc}")

    digest = hashlib.sha256(outside.read_bytes()).hexdigest()
    result = WorkloadResult(
        ok=True,
        artifacts=[ArtifactRef(path="linked.txt", digest_sha256=digest, kind="text")],
    )
    artifacts = WorkloadArtifacts(tmp_path, ReproducibilityEnforcer(tmp_path))

    with pytest.raises(ValueError, match="E_ARTIFACT_SYMLINK_FORBIDDEN"):
        artifacts.validate_sdk_artifacts(result, artifact_root)
    with pytest.raises(ValueError, match="E_ARTIFACT_SYMLINK_FORBIDDEN"):
        artifacts.build_artifact_manifest(artifact_root)


def test_workload_artifacts_validate_sdk_artifacts_emits_deterministic_ordered_payload(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir(parents=True)
    (artifact_root / "ok.txt").write_text("ok", encoding="utf-8")

    result = WorkloadResult(
        ok=True,
        artifacts=[
            ArtifactRef(path="../escape.txt", digest_sha256="0" * 64, kind="text"),
            ArtifactRef(path="ok.txt", digest_sha256="f" * 64, kind="text"),
        ],
    )
    artifacts = WorkloadArtifacts(tmp_path, ReproducibilityEnforcer(tmp_path))
    with pytest.raises(ValueError) as excinfo:
        artifacts.validate_sdk_artifacts(result, artifact_root)
    message = str(excinfo.value)
    assert message.startswith("E_SDK_ARTIFACT_VALIDATION_FAILED:")
    payload = json.loads(message.split(": ", 1)[1])
    errors = payload["errors"]
    assert [row["code"] for row in errors] == ["E_ARTIFACT_PATH_TRAVERSAL", "E_SDK_ARTIFACT_DIGEST_MISMATCH"]
    assert errors[0]["path_norm"] == "../escape.txt"
    assert errors[1]["path_norm"] == "ok.txt"


def test_workload_artifacts_enforces_file_and_total_size_caps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir(parents=True)
    big = artifact_root / "big.bin"
    small = artifact_root / "small.bin"
    big.write_bytes(b"a" * 10)
    small.write_bytes(b"b" * 5)
    big_digest = hashlib.sha256(big.read_bytes()).hexdigest()
    small_digest = hashlib.sha256(small.read_bytes()).hexdigest()
    artifacts = WorkloadArtifacts(tmp_path, ReproducibilityEnforcer(tmp_path))

    monkeypatch.setenv("ORKET_EXT_ARTIFACT_FILE_SIZE_CAP_BYTES", "8")
    with pytest.raises(ValueError, match="E_ARTIFACT_FILE_SIZE_CAP"):
        artifacts.validate_sdk_artifacts(
            WorkloadResult(
                ok=True,
                artifacts=[ArtifactRef(path="big.bin", digest_sha256=big_digest, kind="bin")],
            ),
            artifact_root,
        )

    monkeypatch.setenv("ORKET_EXT_ARTIFACT_FILE_SIZE_CAP_BYTES", "20")
    monkeypatch.setenv("ORKET_EXT_ARTIFACT_TOTAL_SIZE_CAP_BYTES", "12")
    with pytest.raises(ValueError, match="E_ARTIFACT_TOTAL_SIZE_CAP"):
        artifacts.validate_sdk_artifacts(
            WorkloadResult(
                ok=True,
                artifacts=[
                    ArtifactRef(path="big.bin", digest_sha256=big_digest, kind="bin"),
                    ArtifactRef(path="small.bin", digest_sha256=small_digest, kind="bin"),
                ],
            ),
            artifact_root,
        )


def test_workload_artifacts_build_sdk_capability_registry_registers_audio_defaults(tmp_path: Path) -> None:
    artifacts = WorkloadArtifacts(tmp_path, ReproducibilityEnforcer(tmp_path))
    registry = artifacts.build_sdk_capability_registry(
        workspace=tmp_path / "workspace",
        artifact_root=tmp_path / "artifacts",
        input_config={},
    )
    assert isinstance(registry.tts(), NullTTSProvider)
    assert isinstance(registry.audio_player(), NullAudioPlayer)
    assert isinstance(registry.speech_player(), NullAudioPlayer)
    assert isinstance(registry.llm(), LLMProvider)
    assert isinstance(registry.memory_writer(), SQLiteMemoryCapabilityProvider)
    assert isinstance(registry.memory_query(), SQLiteMemoryCapabilityProvider)
    assert isinstance(registry.stt(), HostSTTCapabilityProvider)
    assert isinstance(registry.voice_turn_controller(), HostVoiceTurnController)


def test_workload_artifacts_build_sdk_capability_registry_honors_memory_toggles(tmp_path: Path) -> None:
    """Layer: integration. Verifies runtime memory toggles are propagated into capability provider controls."""
    artifacts = WorkloadArtifacts(tmp_path, ReproducibilityEnforcer(tmp_path))
    registry = artifacts.build_sdk_capability_registry(
        workspace=tmp_path / "workspace",
        artifact_root=tmp_path / "artifacts",
        input_config={"memory": {"session_memory_enabled": False, "profile_memory_enabled": True}},
    )
    provider = registry.memory_writer()

    session_write = provider.write(
        MemoryWriteRequest(scope="session_memory", session_id="s1", key="topic", value="hello")
    )
    assert session_write.ok is False
    assert session_write.error_code == "memory_session_disabled"

    profile_write = provider.write(
        MemoryWriteRequest(scope="profile_memory", key="companion_setting.role_id", value="strategist")
    )
    assert profile_write.ok is True


def test_workload_artifacts_build_sdk_capability_registry_honors_voice_bounds(tmp_path: Path) -> None:
    """Layer: integration. Verifies voice-turn controller receives bounded silence-delay defaults from input config."""
    artifacts = WorkloadArtifacts(tmp_path, ReproducibilityEnforcer(tmp_path))
    registry = artifacts.build_sdk_capability_registry(
        workspace=tmp_path / "workspace",
        artifact_root=tmp_path / "artifacts",
        input_config={
            "voice": {
                "silence_delay_sec": 9.0,
                "silence_delay_min_sec": 0.5,
                "silence_delay_max_sec": 3.0,
            }
        },
    )
    controller = registry.voice_turn_controller()
    assert isinstance(controller, HostVoiceTurnController)
    assert controller.silence_delay_seconds() == 3.0


def test_workload_executor_compile_workload() -> None:
    class _Workload:
        workload_id = "demo_v1"
        workload_version = "1.0.0"

        def compile(self, input_config):
            return RunPlan(workload_id="demo_v1", workload_version="1.0.0", actions=())

    executor = WorkloadExecutor(
        project_root=Path.cwd(),
        reproducibility=ReproducibilityEnforcer(Path.cwd()),
        registry_factory=lambda: None,  # type: ignore[arg-type]
    )
    run_plan = executor._compile_workload(_Workload(), {"seed": 1}, None)
    assert run_plan.workload_id == "demo_v1"


@pytest.mark.asyncio
async def test_extension_engine_adapter_normalizes_legacy_run_ops_to_run_card(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Layer: unit. Verifies extension run actions normalize compatibility ops onto the canonical card surface."""
    calls: list[tuple[str, dict[str, object]]] = []

    class _FakeEngine:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def run_card(self, card_id: str, **kwargs: object) -> dict[str, object]:
            calls.append((card_id, dict(kwargs)))
            return {"card_id": card_id, "kwargs": dict(kwargs)}

    monkeypatch.setattr("orket.extensions.runtime.OrchestrationEngine", _FakeEngine)

    adapter = ExtensionEngineAdapter(RunContext(workspace=tmp_path, department="core"))

    epic_result = await adapter.execute_action(
        RunAction(op="run_epic", target="demo-epic", params={"build_id": "build-1"})
    )
    rock_result = await adapter.execute_action(
        RunAction(op="run_rock", target="demo-rock", params={"build_id": "build-2"})
    )
    issue_result = await adapter.execute_action(
        RunAction(op="run_issue", target="ISSUE-7", params={"session_id": "session-7"})
    )

    assert calls == [
        ("demo-epic", {"build_id": "build-1"}),
        ("demo-rock", {"build_id": "build-2"}),
        ("ISSUE-7", {"session_id": "session-7"}),
    ]
    assert epic_result == {"transcript": {"card_id": "demo-epic", "kwargs": {"build_id": "build-1"}}}
    assert rock_result == {"card_id": "demo-rock", "kwargs": {"build_id": "build-2"}}
    assert issue_result == {"transcript": {"card_id": "ISSUE-7", "kwargs": {"session_id": "session-7"}}}


def test_extension_engine_adapter_treats_run_rock_as_legacy_alias_only() -> None:
    """Layer: unit. Verifies extension runtime keeps `run_rock` as explicit alias normalization, not a primary op set member."""
    runtime_text = (Path("orket/extensions/runtime.py")).read_text(encoding="utf-8-sig")

    assert 'if op in {"run_card", "run_epic", "run_rock", "run_issue"}:' not in runtime_text
    assert 'canonical_op = "run_card" if op in {"run_epic", "run_issue", "run_rock"} else op' in runtime_text


def test_extensions_package_root_does_not_export_manifest_workload_alias() -> None:
    """Layer: unit. Verifies package-root extension exports do not bless workload metadata authority nouns."""
    assert not hasattr(extensions_package, "WorkloadRecord")
    assert not hasattr(extensions_package, "ExtensionManifestWorkload")
    assert not hasattr(extension_manager_module, "ExtensionManifestWorkload")
    assert not hasattr(extension_models, "ExtensionManifestWorkload")
    assert not hasattr(extension_models, "ExtensionWorkloadDescriptor")
    assert not hasattr(extension_models, "WorkloadRecord")


def test_extension_catalog_manifest_lookup_is_internal_only() -> None:
    """Layer: unit. Verifies extension catalog no longer exposes a public-looking manifest lookup method."""
    assert not hasattr(ExtensionCatalog, "resolve_manifest_entry")
    assert hasattr(ExtensionCatalog, "_resolve_manifest_entry")
