from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from orket_extension_sdk.audio import NullAudioPlayer, NullTTSProvider
from orket_extension_sdk.llm import NullLLMProvider
from orket_extension_sdk.memory import NullMemoryProvider
from orket_extension_sdk.result import ArtifactRef, WorkloadResult
from orket_extension_sdk.voice import NullSTTProvider, NullVoiceTurnController

from orket.extensions.catalog import ExtensionCatalog
from orket.extensions.manifest_parser import ManifestParser
from orket.extensions.models import CONTRACT_STYLE_LEGACY
from orket.extensions.reproducibility import ReproducibilityEnforcer
from orket.extensions.workload_artifacts import WorkloadArtifacts
from orket.extensions.workload_executor import WorkloadExecutor
from orket.extensions.workload_loader import WorkloadLoader
from orket.extensions.contracts import RunPlan


def test_extension_catalog_load_and_list(tmp_path: Path) -> None:
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
    assert records[0].workloads[0].workload_id == "demo_v1"


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
    manifest = artifacts.build_artifact_manifest(artifact_root)

    assert manifest["files"][0]["path"] == "a.txt"
    assert len(manifest["manifest_sha256"]) == 64


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
    assert isinstance(registry.llm(), NullLLMProvider)
    assert isinstance(registry.memory_writer(), NullMemoryProvider)
    assert isinstance(registry.memory_query(), NullMemoryProvider)
    assert isinstance(registry.stt(), NullSTTProvider)
    assert isinstance(registry.voice_turn_controller(), NullVoiceTurnController)


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
