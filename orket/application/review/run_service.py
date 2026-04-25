from __future__ import annotations

import asyncio
import logging
import secrets
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Literal
from urllib import parse

from orket.application.review.artifacts import write_review_run_bundle
from orket.application.review.control_plane_projection import validate_review_control_plane_summary
from orket.application.review.errors import ReviewError
from orket.application.review.lanes.deterministic import run_deterministic_lane
from orket.application.review.lanes.model_assisted import ModelProvider, run_model_assisted_lane
from orket.application.review.models import (
    ReviewRunManifest,
    ReviewRunResult,
    ReviewSnapshot,
    SnapshotBounds,
)
from orket.application.review.policy_resolver import resolve_review_policy
from orket.application.review.snapshot_loader import (
    filter_snapshot_paths,
    load_from_diff,
    load_from_files,
    load_from_pr,
)
from orket.application.services.review_run_control_plane_service import (
    ReviewRunControlPlaneService,
    build_review_run_control_plane_service,
)
from orket.capabilities.sync_bridge import run_coro_sync

logger = logging.getLogger(__name__)

GIT_COMMAND_TIMEOUT_SECONDS = 30
_ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ULID_RANDOMNESS_BYTES = 10
_ULID_RANDOMNESS_LIMIT = 1 << 80
_ULID_TIMESTAMP_LIMIT = 1 << 48
_ulid_lock = threading.Lock()
_last_ulid_timestamp_ms = -1
_last_ulid_randomness = -1


def _encode_crockford_base32(value: int, *, length: int) -> str:
    if value < 0:
        raise ValueError("ULID component cannot be negative")
    chars: list[str] = []
    remaining = value
    for _ in range(length):
        chars.append(_ULID_ALPHABET[remaining & 0x1F])
        remaining >>= 5
    if remaining:
        raise ValueError("ULID component exceeds encoded length")
    return "".join(reversed(chars))


def _generate_ulid() -> str:
    global _last_ulid_randomness, _last_ulid_timestamp_ms

    timestamp_ms = time.time_ns() // 1_000_000
    if timestamp_ms >= _ULID_TIMESTAMP_LIMIT:
        raise OverflowError("ULID timestamp exceeds 48-bit range")

    with _ulid_lock:
        if timestamp_ms > _last_ulid_timestamp_ms:
            resolved_timestamp_ms = timestamp_ms
            randomness = int.from_bytes(secrets.token_bytes(_ULID_RANDOMNESS_BYTES), byteorder="big", signed=False)
        else:
            resolved_timestamp_ms = _last_ulid_timestamp_ms
            randomness = (_last_ulid_randomness + 1) % _ULID_RANDOMNESS_LIMIT
            if randomness == 0:
                resolved_timestamp_ms += 1
                if resolved_timestamp_ms >= _ULID_TIMESTAMP_LIMIT:
                    raise OverflowError("ULID timestamp exceeds 48-bit range")

        _last_ulid_timestamp_ms = resolved_timestamp_ms
        _last_ulid_randomness = randomness

    return _encode_crockford_base32(resolved_timestamp_ms, length=10) + _encode_crockford_base32(
        randomness,
        length=16,
    )


def _decision_exit_code(decision: str, fail_on_blocked: bool) -> int:
    if fail_on_blocked and decision == "blocked":
        return 2
    return 0


def _run_git_command(repo_root: Path, args: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
    command = ["git", *args]
    try:
        return subprocess.run(
            command,
            cwd=str(repo_root),
            check=check,
            capture_output=True,
            text=True,
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.CalledProcessError as exc:
        raise ReviewError(
            f"Review git command failed: {' '.join(command)}",
            command=command,
            returncode=exc.returncode,
            stderr=str(exc.stderr or "").strip(),
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ReviewError(
            f"Review git command timed out after {GIT_COMMAND_TIMEOUT_SECONDS}s: {' '.join(command)}",
            command=command,
            stderr=str(exc.stderr or "").strip(),
        ) from exc
    except FileNotFoundError as exc:
        raise ReviewError("Review git command failed: git executable was not found", command=command) from exc


async def _run_git_command_async(
    repo_root: Path,
    args: list[str],
    *,
    check: bool,
) -> subprocess.CompletedProcess[str]:
    return await asyncio.to_thread(_run_git_command, repo_root, args, check=check)


def _git_paths(repo_root: Path, base_ref: str, head_ref: str) -> list[str]:
    proc = run_coro_sync(_run_git_command_async(repo_root, ["diff", "--name-only", base_ref, head_ref], check=True))
    return [line.strip().replace("\\", "/") for line in proc.stdout.splitlines() if line.strip()]


def _normalize_extensions(values: list[str]) -> set[str]:
    out = set()
    for item in values:
        token = str(item or "").strip().lower()
        if not token:
            continue
        out.add(token if token.startswith(".") else f".{token}")
    return out


def _filter_code_paths(paths: list[str], extensions: set[str]) -> list[str]:
    if not extensions:
        return list(paths)
    keep: list[str] = []
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


def _normalize_repo_slug(repo: str) -> str:
    return str(repo or "").strip().strip("/").removesuffix(".git")


def _normalize_host_port(hostname: str | None, port: int | None) -> str:
    host = str(hostname or "").strip().lower()
    if not host:
        return ""
    return f"{host}:{int(port)}" if port else host


def _parse_repo_remote_binding(raw_url: str, *, repo: str) -> tuple[str, str] | None:
    token = str(raw_url or "").strip()
    if not token:
        return None

    repo_slug = _normalize_repo_slug(repo)
    host = ""
    repo_path = ""

    if "://" in token:
        parsed = parse.urlparse(token)
        host = _normalize_host_port(parsed.hostname, parsed.port)
        repo_path = str(parsed.path or "").strip().strip("/")
    elif "@" in token and ":" in token.split("@", 1)[-1]:
        authority, _, repo_path = token.partition(":")
        host = str(authority.split("@", 1)[-1] or "").strip().lower()
        repo_path = str(repo_path or "").strip().strip("/")
    else:
        return None

    normalized_repo_path = repo_path.removesuffix(".git").strip("/")
    if not host or not normalized_repo_path:
        return None
    if normalized_repo_path == repo_slug:
        return host, ""
    suffix = f"/{repo_slug}"
    if normalized_repo_path.endswith(suffix):
        return host, normalized_repo_path[: -len(suffix)].strip("/")
    return None


def _configured_review_remote_bindings(repo_root: Path, *, repo: str) -> set[tuple[str, str]]:
    proc = run_coro_sync(
        _run_git_command_async(repo_root, ["config", "--get-regexp", r"^remote\..*\.url$"], check=False)
    )
    if proc.returncode not in {0, 1}:
        detail = str(proc.stderr or "").strip() or "git remote lookup failed"
        raise ValueError(f"Review PR mode requires a git repo with configured remotes: {detail}")

    bindings: set[tuple[str, str]] = set()
    for line in proc.stdout.splitlines():
        _, _, raw_url = line.partition(" ")
        binding = _parse_repo_remote_binding(raw_url.strip(), repo=repo)
        if binding is not None:
            bindings.add(binding)
    return bindings


def _resolve_bound_pr_remote(*, remote: str, repo_root: Path, repo: str) -> str:
    parsed = parse.urlparse(str(remote or "").strip())
    scheme = str(parsed.scheme or "").strip().lower()
    if scheme not in {"http", "https"}:
        raise ValueError("Review PR remote must be an http(s) base URL.")
    host = _normalize_host_port(parsed.hostname, parsed.port)
    if not host:
        raise ValueError("Review PR remote must include a hostname.")
    base_path = str(parsed.path or "").strip().strip("/")
    normalized_remote = f"{scheme}://{host}"
    if base_path:
        normalized_remote = f"{normalized_remote}/{base_path}"

    configured = _configured_review_remote_bindings(repo_root, repo=repo)
    if not configured:
        raise ValueError(f"Review PR remote is unbound: no configured git remote matches repo '{repo}'.")
    if (host, base_path) not in configured:
        raise ValueError(
            f"Review PR remote '{normalized_remote}' is not bound to a configured git remote for repo '{repo}'."
        )
    return normalized_remote


class ReviewRunService:
    def __init__(
        self,
        *,
        workspace: Path,
        control_plane_db_path: Path | None = None,
        review_control_plane_service: ReviewRunControlPlaneService | None = None,
    ):
        self.workspace = workspace
        self.review_control_plane_service = review_control_plane_service or build_review_run_control_plane_service(
            db_path=control_plane_db_path
        )

    def run_pr(
        self,
        *,
        remote: str,
        repo: str,
        pr: int,
        repo_root: Path,
        bounds: SnapshotBounds,
        cli_policy_overrides: dict[str, Any] | None = None,
        policy_path: Path | None = None,
        fail_on_blocked: bool = False,
        token: str = "",
        model_provider: ModelProvider | None = None,
    ) -> ReviewRunResult:
        resolved_policy = resolve_review_policy(
            cli_overrides=cli_policy_overrides,
            repo_root=repo_root,
            policy_path=policy_path,
        )
        scope = dict(resolved_policy.payload.get("input_scope") or {})
        scope_mode = str(scope.get("mode") or "code_only").strip().lower()
        ext_set = _normalize_extensions(list(scope.get("code_extensions") or []))
        bound_remote = _resolve_bound_pr_remote(remote=remote, repo_root=repo_root, repo=repo)
        resolved_token, auth_source = _resolve_token(token)
        snapshot = load_from_pr(
            remote=bound_remote,
            repo=repo,
            pr_number=pr,
            bounds=bounds,
            token=resolved_token,
            metadata={"pr_number": int(pr)},
        )
        if scope_mode == "code_only":
            code_paths = _filter_code_paths([item.path for item in snapshot.changed_files], ext_set)
            snapshot = filter_snapshot_paths(snapshot, set(code_paths))
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
        cli_policy_overrides: dict[str, Any] | None = None,
        policy_path: Path | None = None,
        fail_on_blocked: bool = False,
        model_provider: ModelProvider | None = None,
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
        paths: list[str],
        bounds: SnapshotBounds,
        cli_policy_overrides: dict[str, Any] | None = None,
        policy_path: Path | None = None,
        fail_on_blocked: bool = False,
        model_provider: ModelProvider | None = None,
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
        resolved_policy_payload: dict[str, Any],
        fail_on_blocked: bool = False,
        model_provider: ModelProvider | None = None,
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
        model_provider: ModelProvider | None,
    ) -> ReviewRunResult:
        run_id = _generate_ulid()
        artifact_dir = self.workspace / "review_runs" / run_id
        control_plane_attempt_id = ""
        control_plane_step_id = ""
        try:
            _, control_plane_attempt, control_plane_step, _control_plane_checkpoint = run_coro_sync(
                self.review_control_plane_service.begin_execution(
                    run_id=run_id,
                    snapshot=snapshot,
                    resolved_policy_payload=resolved_policy.payload,
                    auth_source=auth_source,
                    model_assisted_enabled=bool((resolved_policy.payload.get("model_assisted") or {}).get("enabled")),
                )
            )
            control_plane_attempt_id = control_plane_attempt.attempt_id
            control_plane_step_id = control_plane_step.step_id
            deterministic = run_deterministic_lane(
                snapshot=snapshot,
                resolved_policy=resolved_policy.payload,
                run_id=run_id,
                policy_digest=resolved_policy.policy_digest,
            )
            deterministic.control_plane_run_id = run_id
            deterministic.control_plane_attempt_id = control_plane_attempt_id
            deterministic.control_plane_step_id = control_plane_step_id
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
                model_result.control_plane_run_id = run_id
                model_result.control_plane_attempt_id = control_plane_attempt_id
                model_result.control_plane_step_id = control_plane_step_id

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
                execution_state_authority="control_plane_records",
                lane_outputs_execution_state_authoritative=False,
                control_plane_run_id=run_id,
                control_plane_attempt_id=control_plane_attempt_id,
                control_plane_step_id=control_plane_step_id,
            )
            write_review_run_bundle(
                artifact_dir=artifact_dir,
                snapshot=snapshot,
                resolved_policy=resolved_policy,
                deterministic=deterministic,
                model_assisted=model_result,
                manifest=manifest,
            )
            run_coro_sync(self.review_control_plane_service.finalize_completed(run_id=run_id))
            control_plane_summary = validate_review_control_plane_summary(
                run_coro_sync(self.review_control_plane_service.read_execution_summary(run_id=run_id)),
                expected_run_id=run_id,
                expected_attempt_id=control_plane_attempt_id,
                expected_step_id=control_plane_step_id,
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
                control_plane=control_plane_summary,
                exit_code=exit_code,
            )
        except Exception as exc:
            failure_class = f"review_run_{type(exc).__name__}"[:200]
            finalized = run_coro_sync(
                self.review_control_plane_service.finalize_failed_if_started(
                    run_id=run_id,
                    failure_class=failure_class,
                )
            )
            if control_plane_attempt_id and finalized is None:
                logger.error("Review run control-plane closeout was skipped after begin_execution: run_id=%s", run_id)
            raise
