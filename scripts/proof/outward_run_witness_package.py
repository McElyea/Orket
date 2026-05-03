from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.proof.outward_run_witness_contract import (
    BUNDLE_ONLY_BLOCKER,
    BUNDLE_SCHEMA_VERSION,
    DEFAULT_BUNDLE_PATH,
    DEFAULT_LEDGER_EXPORT_PATH,
    PACKAGE_SCHEMA_VERSION,
    compute_package_digest,
    file_sha256,
    load_json_object,
)


@dataclass(frozen=True)
class OutwardRunWitnessPackage:
    root: Path
    manifest: dict[str, Any]
    bundle: dict[str, Any]
    ledger_export: dict[str, Any]
    artifacts: dict[str, bytes]
    file_digests: dict[str, str]


@dataclass(frozen=True)
class PackageLoadResult:
    ok: bool
    failure_code: str | None
    package: OutwardRunWitnessPackage | None = None


def load_witness_package(package_root: Path) -> PackageLoadResult:
    root = package_root.resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        return _failure("package_manifest_missing")
    try:
        manifest = load_json_object(manifest_path)
    except (OSError, ValueError):
        return _failure("package_manifest_missing")
    if manifest.get("schema_version") != PACKAGE_SCHEMA_VERSION:
        return _failure("package_manifest_digest_mismatch")

    bundle_path = _resolve_package_ref(root, manifest.get("bundle_path") or DEFAULT_BUNDLE_PATH)
    if bundle_path is None:
        return _failure("package_ref_outside_package")
    if not bundle_path.exists():
        return _failure("bundle_missing")

    ledger_path = _resolve_package_ref(root, manifest.get("ledger_export_path") or DEFAULT_LEDGER_EXPORT_PATH)
    if ledger_path is None:
        return _failure("package_ref_outside_package")
    if not ledger_path.exists():
        return _failure("ledger_export_missing")

    raw_artifact_paths = manifest.get("artifact_paths")
    artifact_paths = raw_artifact_paths if isinstance(raw_artifact_paths, dict) else {}
    resolved_artifacts: dict[str, Path] = {}
    for role, ref in artifact_paths.items():
        artifact_path = _resolve_package_ref(root, ref)
        if artifact_path is None:
            return _failure("package_ref_outside_package")
        resolved_artifacts[str(role)] = artifact_path

    try:
        bundle = load_json_object(bundle_path)
        ledger_export = load_json_object(ledger_path)
    except (OSError, ValueError):
        return _failure("package_manifest_digest_mismatch")
    if _bundle_package_ref_escaped(root, bundle):
        return _failure("package_ref_outside_package")

    try:
        artifacts = {role: path.read_bytes() for role, path in resolved_artifacts.items() if path.exists()}
    except OSError:
        return _failure("package_manifest_digest_mismatch")

    file_digests = _package_file_digests(root, bundle_path, ledger_path, resolved_artifacts)
    declared_digests = manifest.get("file_digests")
    if not isinstance(declared_digests, dict) or not _declared_digests_match(declared_digests, file_digests):
        return _failure("package_manifest_digest_mismatch")
    if manifest.get("package_digest") != compute_package_digest(manifest):
        return _failure("package_manifest_digest_mismatch")

    return PackageLoadResult(
        ok=True,
        failure_code=None,
        package=OutwardRunWitnessPackage(
            root=root,
            manifest=manifest,
            bundle=bundle,
            ledger_export=ledger_export,
            artifacts=artifacts,
            file_digests=file_digests,
        ),
    )


def bundle_only_introspection(bundle: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if bundle.get("schema_version") != BUNDLE_SCHEMA_VERSION:
        failures.append("bundle_schema_missing_or_unsupported")
    failures.append(BUNDLE_ONLY_BLOCKER)
    return {
        "schema_version": "outward_run_bundle_introspection.v1",
        "result": "downgraded",
        "accepted": False,
        "missing_evidence": failures,
    }


def _failure(code: str) -> PackageLoadResult:
    return PackageLoadResult(ok=False, failure_code=code)


def _resolve_package_ref(root: Path, ref: Any) -> Path | None:
    clean = str(ref or "").strip()
    if not clean:
        return None
    resolved = (root / clean).resolve()
    return resolved if resolved.is_relative_to(root) else None


def _package_file_digests(
    root: Path,
    bundle_path: Path,
    ledger_path: Path,
    artifacts: dict[str, Path],
) -> dict[str, str]:
    paths = [bundle_path, ledger_path, *artifacts.values()]
    return {path.relative_to(root).as_posix(): file_sha256(path) for path in paths if path.exists()}


def _declared_digests_match(declared: dict[str, Any], actual: dict[str, str]) -> bool:
    for path, digest in actual.items():
        if declared.get(path) != digest:
            return False
    return DEFAULT_BUNDLE_PATH in declared and DEFAULT_LEDGER_EXPORT_PATH in declared


def _bundle_package_ref_escaped(root: Path, bundle: dict[str, Any]) -> bool:
    package_refs = bundle.get("package_refs")
    if isinstance(package_refs, dict):
        for ref in package_refs.values():
            if _resolve_package_ref(root, ref) is None:
                return True
    for ref in bundle.get("artifact_refs") or []:
        if not isinstance(ref, dict):
            continue
        package_ref = ref.get("package_path") or ref.get("package_ref")
        if package_ref and _resolve_package_ref(root, package_ref) is None:
            return True
    return False
