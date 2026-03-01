from __future__ import annotations

import secrets
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from orket.application.review.artifacts import write_review_run_bundle
from orket.application.review.lanes.deterministic import run_deterministic_lane
from orket.application.review.lanes.model_assisted import ModelProvider, run_model_assisted_lane
from orket.application.review.models import (
    ReviewRunManifest,
    ReviewRunResult,
    ReviewSnapshot,
    SnapshotBounds,
)
from orket.application.review.policy_resolver import resolve_review_policy
from orket.application.review.snapshot_loader import load_from_diff, load_from_files, load_from_pr


def _ulid() -> str:
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    timestamp_ms = int(time.time() * 1000)
    time_chars: List[str] = []
    value = timestamp_ms
    for _ in range(10):
        time_chars.append(alphabet[value % 32])
        value //= 32
    random_value = int.from_bytes(secrets.token_bytes(10), byteorder="big", signed=False)
    rand_chars: List[str] = []
    for _ in range(16):
        rand_chars.append(alphabet[random_value % 32])
        random_value //= 32
    return "".join(reversed(time_chars)) + "".join(reversed(rand_chars))


def _decision_exit_code(decision: str, fail_on_blocked: bool) -> int:
    if fail_on_blocked and decision == "blocked":
        return 2
    return 0


def _git_paths(repo_root: Path, base_ref: str, head_ref: str) -> List[str]:
    proc = subprocess.run(
        ["git", "diff", "--name-only", base_ref, head_ref],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip().replace("\\", "/") for line in proc.stdout.splitlines() if line.strip()]


def _normalize_extensions(values: List[str]) -> set[str]:
    out = set()
    for item in values:
        token = str(item or "").strip().lower()
        if not token:
            continue
        out.add(token if token.startswith(".") else f".{token}")
    return out


def _filter_code_paths(paths: List[str], extensions: set[str]) -> List[str]:
    if not extensions:
        return list(paths)
    keep: List[str] = []
    for path in paths:
        suffix = Path(path).suffix.lower()
        if suffix in extensions:
            keep.append(path)
    return keep


def _resolve_token(cli_token: str) -> tuple[str, Literal["token_flag", "token_env", "none"]]:
    token = str(cli_token or "").strip()
    if token:
        return token, "token_flag"
    import os

    env_token = str(os.getenv("ORKET_GITEA_TOKEN") or "").strip()
    if env_token:
        return env_token, "token_env"
    alias_token = str(os.getenv("GITEA_TOKEN") or "").strip()
    if alias_token:
        return alias_token, "token_env"
    return "", "none"


class ReviewRunService:
    def __init__(self, *, workspace: Path):
        self.workspace = workspace

    def run_pr(
        self,
        *,
        remote: str,
        repo: str,
        pr: int,
        repo_root: Path,
        bounds: SnapshotBounds,
        cli_policy_overrides: Optional[Dict[str, Any]] = None,
        policy_path: Optional[Path] = None,
        fail_on_blocked: bool = False,
        token: str = "",
        model_provider: Optional[ModelProvider] = None,
    ) -> ReviewRunResult:
        resolved_policy = resolve_review_policy(
            cli_overrides=cli_policy_overrides,
            repo_root=repo_root,
            policy_path=policy_path,
        )
        scope = dict(resolved_policy.payload.get("input_scope") or {})
        scope_mode = str(scope.get("mode") or "code_only").strip().lower()
        ext_set = _normalize_extensions(list(scope.get("code_extensions") or []))
        resolved_token, auth_source = _resolve_token(token)
        snapshot = load_from_pr(
            remote=remote,
            repo=repo,
            pr_number=pr,
            bounds=bounds,
            token=resolved_token,
            metadata={"pr_number": int(pr)},
        )
        if scope_mode == "code_only":
            code_paths = _filter_code_paths([item.path for item in snapshot.changed_files], ext_set)
            snapshot = load_from_pr(
                remote=remote,
                repo=repo,
                pr_number=pr,
                bounds=bounds,
                token=resolved_token,
                include_paths=set(code_paths),
                metadata={"pr_number": int(pr)},
            )
        return self._execute(
            snapshot=snapshot,
            resolved_policy=resolved_policy,
            fail_on_blocked=fail_on_blocked,
            auth_source=auth_source,
            model_provider=model_provider,
        )

    def run_diff(
        self,
        *,
        repo_root: Path,
        base_ref: str,
        head_ref: str,
        bounds: SnapshotBounds,
        cli_policy_overrides: Optional[Dict[str, Any]] = None,
        policy_path: Optional[Path] = None,
        fail_on_blocked: bool = False,
        model_provider: Optional[ModelProvider] = None,
    ) -> ReviewRunResult:
        resolved_policy = resolve_review_policy(
            cli_overrides=cli_policy_overrides,
            repo_root=repo_root,
            policy_path=policy_path,
        )
        scope = dict(resolved_policy.payload.get("input_scope") or {})
        scope_mode = str(scope.get("mode") or "code_only").strip().lower()
        ext_set = _normalize_extensions(list(scope.get("code_extensions") or []))
        include_paths = None
        if scope_mode == "code_only":
            include_paths = set(_filter_code_paths(_git_paths(repo_root, base_ref, head_ref), ext_set))
        snapshot = load_from_diff(
            repo_root=repo_root,
            base_ref=base_ref,
            head_ref=head_ref,
            bounds=bounds,
            include_paths=include_paths,
            metadata={},
        )
        return self._execute(
            snapshot=snapshot,
            resolved_policy=resolved_policy,
            fail_on_blocked=fail_on_blocked,
            auth_source="none",
            model_provider=model_provider,
        )

    def run_files(
        self,
        *,
        repo_root: Path,
        ref: str,
        paths: List[str],
        bounds: SnapshotBounds,
        cli_policy_overrides: Optional[Dict[str, Any]] = None,
        policy_path: Optional[Path] = None,
        fail_on_blocked: bool = False,
        model_provider: Optional[ModelProvider] = None,
    ) -> ReviewRunResult:
        resolved_policy = resolve_review_policy(
            cli_overrides=cli_policy_overrides,
            repo_root=repo_root,
            policy_path=policy_path,
        )
        scope = dict(resolved_policy.payload.get("input_scope") or {})
        scope_mode = str(scope.get("mode") or "code_only").strip().lower()
        ext_set = _normalize_extensions(list(scope.get("code_extensions") or []))
        effective_paths = list(paths)
        if scope_mode == "code_only":
            effective_paths = _filter_code_paths(effective_paths, ext_set)
        snapshot = load_from_files(
            repo_root=repo_root,
            ref=ref,
            paths=effective_paths,
            bounds=bounds,
            metadata={},
        )
        return self._execute(
            snapshot=snapshot,
            resolved_policy=resolved_policy,
            fail_on_blocked=fail_on_blocked,
            auth_source="none",
            model_provider=model_provider,
        )

    def replay(
        self,
        *,
        repo_root: Path,
        snapshot: ReviewSnapshot,
        resolved_policy_payload: Dict[str, Any],
        fail_on_blocked: bool = False,
        model_provider: Optional[ModelProvider] = None,
    ) -> ReviewRunResult:
        from orket.application.review.models import ResolvedPolicy, digest_sha256_prefixed, to_canonical_json_bytes

        resolved_policy = ResolvedPolicy(
            payload=dict(resolved_policy_payload),
            policy_digest=digest_sha256_prefixed(to_canonical_json_bytes(resolved_policy_payload)),
        )
        return self._execute(
            snapshot=snapshot,
            resolved_policy=resolved_policy,
            fail_on_blocked=fail_on_blocked,
            auth_source="none",
            model_provider=model_provider,
        )

    def _execute(
        self,
        *,
        snapshot: ReviewSnapshot,
        resolved_policy: Any,
        fail_on_blocked: bool,
        auth_source: Literal["token_flag", "token_env", "none"],
        model_provider: Optional[ModelProvider],
    ) -> ReviewRunResult:
        run_id = _ulid()
        artifact_dir = self.workspace / "review_runs" / run_id

        deterministic = run_deterministic_lane(
            snapshot=snapshot,
            resolved_policy=resolved_policy.payload,
            run_id=run_id,
            policy_digest=resolved_policy.policy_digest,
        )
        model_cfg = dict(resolved_policy.payload.get("model_assisted") or {})
        model_enabled = bool(model_cfg.get("enabled") or False)
        model_result = None
        if model_enabled:
            model_result = run_model_assisted_lane(
                snapshot=snapshot,
                resolved_policy=resolved_policy.payload,
                run_id=run_id,
                policy_digest=resolved_policy.policy_digest,
                provider=model_provider,
            )

        manifest = ReviewRunManifest(
            run_id=run_id,
            snapshot_digest=snapshot.snapshot_digest,
            policy_digest=resolved_policy.policy_digest,
            review_run_contract_version="review_run_v0",
            deterministic_lane_version="deterministic_v0",
            model_lane_contract_version="review_critique_v0" if model_enabled else "",
            bounds=snapshot.bounds.to_dict(),
            truncation=snapshot.truncation.to_dict(),
            auth_source=auth_source,
        )
        write_review_run_bundle(
            artifact_dir=artifact_dir,
            snapshot=snapshot,
            resolved_policy=resolved_policy,
            deterministic=deterministic,
            model_assisted=model_result,
            manifest=manifest,
        )
        exit_code = _decision_exit_code(deterministic.decision, fail_on_blocked)
        return ReviewRunResult(
            ok=True,
            run_id=run_id,
            artifact_dir=str(artifact_dir),
            snapshot_digest=snapshot.snapshot_digest,
            policy_digest=resolved_policy.policy_digest,
            deterministic_decision=deterministic.decision,
            deterministic_findings=len(deterministic.findings),
            model_assisted_enabled=model_enabled,
            manifest=manifest.to_dict(),
            exit_code=exit_code,
        )
