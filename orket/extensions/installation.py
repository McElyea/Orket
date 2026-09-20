"""Admit an isolated checkout before publishing its catalog pointer."""
from __future__ import annotations

from collections.abc import Mapping
from functools import partial
from pathlib import Path

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.extension_install_store import allocate_checkout, sha256_file
from orket.application.services.governed_agent_admission import validate_governed_agent_host_features
from orket_extension_sdk.manifest import ExtensionManifest

from .catalog import ExtensionCatalog
from .git_commands import resolve_commit, run_git
from .manifest_parser import ManifestParser
from .models import CONTRACT_STYLE_SDK_V0, ExtensionRecord
from .source_policy import SourcePolicyDecision, evaluate_source_policy


async def install_extension(*, repo: str, ref: str, install_root: Path, project_root: Path,
                            catalog: ExtensionCatalog, parser: ManifestParser,
                            environment: Mapping[str, str], installed_at_utc: str) -> ExtensionRecord:
    repo, ref = str(repo or "").strip(), str(ref or "").strip()
    if not repo:
        raise ValueError("repo is required")
    policy = evaluate_source_policy(repo, environment)
    destination = await run_owned_thread(partial(allocate_checkout, install_root), label="extension-checkout-allocation")
    await run_git(["clone", "--", repo, str(destination)], cwd=project_root,
                  environment=environment, timeout_seconds=120, code="E_EXT_CLONE_FAILED")
    commit = await resolve_commit(destination, ref, environment=environment)
    await run_git([f"--git-dir={destination / '.git'}", f"--work-tree={destination}",
                   "checkout", "--detach", commit], cwd=destination, environment=environment)
    record = await run_owned_thread(partial(
        _admit_checkout, parser=parser, destination=destination, repo=repo, ref=ref,
        commit=commit, policy=policy, installed_at_utc=installed_at_utc), label="extension-manifest-admission")
    # Publication owns its read/modify/write and readback under one native lock.
    # An interrupted publication is drained and can have a verified durable effect.
    await run_owned_thread(partial(catalog.publish_record, record), label="extension-catalog-publication")
    return record


def _admit_checkout(*, parser: ManifestParser, destination: Path, repo: str, ref: str,
                    commit: str, policy: SourcePolicyDecision, installed_at_utc: str) -> ExtensionRecord:
    loaded = parser.load_manifest(destination)
    if loaded.contract_style == CONTRACT_STYLE_SDK_V0:
        validate_governed_agent_host_features(ExtensionManifest.model_validate(loaded.payload))
    return parser.record_from_manifest(
        loaded.payload, source=repo, path=destination, contract_style=loaded.contract_style,
        manifest_path=loaded.manifest_path, resolved_commit_sha=commit,
        manifest_digest_sha256=sha256_file(loaded.manifest_path), source_ref=ref,
        trust_profile=policy.trust_profile, installed_at_utc=installed_at_utc,
        security_mode=policy.security_mode, security_profile=policy.security_profile,
        security_policy_version=policy.security_policy_version, compat_fallbacks=policy.compat_fallbacks)
