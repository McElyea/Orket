from __future__ import annotations

import subprocess
from pathlib import Path

import httpx

from orket.application.review.errors import ReviewError
from orket.application.review.models import (
    ChangedFile,
    ContextBlob,
    ReviewSnapshot,
    SnapshotBounds,
    TruncationReport,
)

GIT_COMMAND_TIMEOUT_SECONDS = 30


def _run_git(repo_root: Path, args: list[str]) -> str:
    command = ["git", *args]
    try:
        proc = subprocess.run(
            command,
            cwd=str(repo_root),
            check=True,
            capture_output=True,
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace").strip() if exc.stderr else ""
        raise ReviewError(
            f"Review git command failed: {' '.join(command)}",
            command=command,
            returncode=exc.returncode,
            stderr=stderr,
        ) from exc
    except subprocess.TimeoutExpired as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace").strip() if isinstance(exc.stderr, bytes) else str(exc.stderr or "")
        raise ReviewError(
            f"Review git command timed out after {GIT_COMMAND_TIMEOUT_SECONDS}s: {' '.join(command)}",
            command=command,
            stderr=stderr,
        ) from exc
    except FileNotFoundError as exc:
        raise ReviewError("Review git command failed: git executable was not found", command=command) from exc
    return proc.stdout.decode("utf-8", errors="replace")


def _truncate_bytes(text: str, max_bytes: int) -> tuple[str, int, int, bool]:
    encoded = text.encode("utf-8")
    original = len(encoded)
    if original <= max_bytes:
        return text, original, original, False
    kept = encoded[: max(0, int(max_bytes))]
    truncated = kept.decode("utf-8", errors="ignore")
    return truncated, original, len(kept), True


def _split_unified_diff_sections(diff_unified: str) -> list[tuple[str, str]]:
    lines = diff_unified.splitlines(keepends=True)
    sections: list[tuple[str, str]] = []
    current: list[str] = []
    current_path = ""
    for line in lines:
        if line.startswith("diff --git "):
            if current:
                sections.append((current_path, "".join(current)))
                current = []
            current_path = ""
        if line.startswith("+++ "):
            rhs = line[4:].strip()
            if rhs.startswith("b/"):
                rhs = rhs[2:]
            current_path = rhs
        current.append(line)
    if current:
        sections.append((current_path, "".join(current)))
    return sections


def _filter_diff_to_paths(diff_unified: str, include_paths: set[str]) -> str:
    if not include_paths:
        return ""
    chunks = _split_unified_diff_sections(diff_unified)
    filtered = [chunk for path, chunk in chunks if path in include_paths]
    return "".join(filtered)


def _apply_bounds(
    *,
    changed_files: list[ChangedFile],
    diff_unified: str,
    context_blobs: list[ContextBlob],
    bounds: SnapshotBounds,
) -> tuple[list[ChangedFile], str, list[ContextBlob], TruncationReport]:
    notes: list[str] = []

    ordered_files = sorted(changed_files, key=lambda item: (item.path, item.status))
    files_truncated = 0
    if len(ordered_files) > bounds.max_files:
        files_truncated = len(ordered_files) - bounds.max_files
        ordered_files = ordered_files[: bounds.max_files]
        notes.append(f"changed_files truncated by {files_truncated}")

    bounded_diff, diff_orig, diff_kept, diff_truncated = _truncate_bytes(diff_unified, bounds.max_diff_bytes)
    if diff_truncated:
        notes.append("diff_unified truncated by max_diff_bytes")

    bounded_blobs: list[ContextBlob] = []
    blob_original_bytes = 0
    blob_kept_bytes = 0
    blob_truncated = False
    for blob in context_blobs:
        bounded_content, orig, kept, truncated = _truncate_bytes(blob.content, bounds.max_file_bytes)
        blob_original_bytes += orig
        blob_kept_bytes += kept
        if truncated:
            blob_truncated = True
            notes.append(f"context_blob truncated for {blob.path}")
        bounded_blobs.append(
            ContextBlob(
                path=blob.path,
                content=bounded_content,
                truncated=truncated,
                omitted_bytes=max(0, orig - kept),
            )
        )

    if blob_kept_bytes > bounds.max_blob_bytes:
        running = 0
        trimmed: list[ContextBlob] = []
        for blob in bounded_blobs:
            blob_bytes = len(blob.content.encode("utf-8"))
            if running + blob_bytes <= bounds.max_blob_bytes:
                trimmed.append(blob)
                running += blob_bytes
                continue
            remaining = max(0, bounds.max_blob_bytes - running)
            head, _, kept, truncated = _truncate_bytes(blob.content, remaining)
            trimmed.append(
                ContextBlob(
                    path=blob.path,
                    content=head,
                    truncated=True,
                    omitted_bytes=max(0, blob_bytes - kept),
                )
            )
            running += kept
            blob_truncated = True
            break
        bounded_blobs = trimmed
        blob_kept_bytes = min(blob_kept_bytes, bounds.max_blob_bytes)
        notes.append("context_blobs truncated by max_blob_bytes")

    truncation = TruncationReport(
        files_truncated=files_truncated,
        diff_bytes_original=diff_orig,
        diff_bytes_kept=diff_kept,
        diff_truncated=diff_truncated,
        blob_bytes_original=blob_original_bytes,
        blob_bytes_kept=blob_kept_bytes,
        blob_truncated=blob_truncated,
        notes=notes,
    )
    return ordered_files, bounded_diff, bounded_blobs, truncation


def _parse_name_status(text: str) -> dict[str, str]:
    status_map: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        raw_status = parts[0].strip()
        path = parts[-1] if raw_status.startswith("R") and len(parts) >= 3 else parts[1]
        status_map[path] = raw_status
    return status_map


def _parse_numstat(text: str) -> dict[str, tuple[int, int]]:
    out: dict[str, tuple[int, int]] = {}
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        adds_raw, dels_raw, path = parts
        adds = int(adds_raw) if adds_raw.isdigit() else 0
        dels = int(dels_raw) if dels_raw.isdigit() else 0
        out[path] = (adds, dels)
    return out


def load_from_diff(
    *,
    repo_root: Path,
    base_ref: str,
    head_ref: str,
    bounds: SnapshotBounds,
    include_paths: set[str] | None = None,
    metadata: dict[str, object] | None = None,
) -> ReviewSnapshot:
    name_status = _run_git(repo_root, ["diff", "--name-status", base_ref, head_ref])
    numstat = _run_git(repo_root, ["diff", "--numstat", base_ref, head_ref])
    unified = _run_git(repo_root, ["diff", "--unified=3", base_ref, head_ref])

    status_map = _parse_name_status(name_status)
    numstat_map = _parse_numstat(numstat)
    all_paths = sorted(set(status_map.keys()) | set(numstat_map.keys()))
    if include_paths is not None:
        all_paths = [path for path in all_paths if path in include_paths]
    changed_files = [
        ChangedFile(
            path=path,
            status=str(status_map.get(path) or "M"),
            additions=int(numstat_map.get(path, (0, 0))[0]),
            deletions=int(numstat_map.get(path, (0, 0))[1]),
        )
        for path in all_paths
    ]
    if include_paths is not None:
        unified = _filter_diff_to_paths(unified, include_paths)
    bounded_files, bounded_diff, bounded_blobs, truncation = _apply_bounds(
        changed_files=changed_files,
        diff_unified=unified,
        context_blobs=[],
        bounds=bounds,
    )

    snapshot = ReviewSnapshot(
        source="diff",
        repo={"remote": "", "repo_id": str(repo_root.resolve())},
        base_ref=str(base_ref),
        head_ref=str(head_ref),
        bounds=bounds,
        truncation=truncation,
        changed_files=bounded_files,
        diff_unified=bounded_diff,
        context_blobs=bounded_blobs,
        metadata=dict(metadata or {}),
    )
    snapshot.compute_snapshot_digest()
    return snapshot


def load_from_files(
    *,
    repo_root: Path,
    ref: str,
    paths: list[str],
    bounds: SnapshotBounds,
    include_paths: set[str] | None = None,
    metadata: dict[str, object] | None = None,
) -> ReviewSnapshot:
    changed_files: list[ChangedFile] = []
    context_blobs: list[ContextBlob] = []
    diff_blocks: list[str] = []
    selected_paths = sorted(set(paths))
    if include_paths is not None:
        selected_paths = [path for path in selected_paths if path in include_paths]
    for raw_path in selected_paths:
        path = raw_path.strip().replace("\\", "/")
        if not path:
            continue
        try:
            content = _run_git(repo_root, ["show", f"{ref}:{path}"])
        except ReviewError:
            raise
        changed_files.append(ChangedFile(path=path, status="selected", additions=0, deletions=0))
        context_blobs.append(ContextBlob(path=path, content=content))
        diff_blocks.append(f"*** FILE {path} @ {ref}\n{content}")

    unified = "\n".join(diff_blocks)
    bounded_files, bounded_diff, bounded_blobs, truncation = _apply_bounds(
        changed_files=changed_files,
        diff_unified=unified,
        context_blobs=context_blobs,
        bounds=bounds,
    )
    snapshot = ReviewSnapshot(
        source="files",
        repo={"remote": "", "repo_id": str(repo_root.resolve())},
        base_ref=str(ref),
        head_ref=str(ref),
        bounds=bounds,
        truncation=truncation,
        changed_files=bounded_files,
        diff_unified=bounded_diff,
        context_blobs=bounded_blobs,
        metadata=dict(metadata or {}),
    )
    snapshot.compute_snapshot_digest()
    return snapshot


def load_from_pr(
    *,
    remote: str,
    repo: str,
    pr_number: int,
    bounds: SnapshotBounds,
    token: str = "",
    include_paths: set[str] | None = None,
    metadata: dict[str, object] | None = None,
) -> ReviewSnapshot:
    base = remote.rstrip("/")
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"token {token}"
    with httpx.Client(timeout=20.0, headers=headers) as client:
        pr_url = f"{base}/api/v1/repos/{repo}/pulls/{int(pr_number)}"
        pr_resp = client.get(pr_url)
        pr_resp.raise_for_status()
        pr_payload = pr_resp.json()

        files_url = f"{base}/api/v1/repos/{repo}/pulls/{int(pr_number)}/files"
        files_resp = client.get(files_url)
        files_resp.raise_for_status()
        files_payload = files_resp.json() if isinstance(files_resp.json(), list) else []

        diff_url = f"{base}/api/v1/repos/{repo}/pulls/{int(pr_number)}.diff"
        diff_resp = client.get(diff_url, headers={"Accept": "text/plain", **headers})
        diff_resp.raise_for_status()
        unified = str(diff_resp.text or "")

    changed_files: list[ChangedFile] = []
    for item in files_payload:
        path = str(item.get("filename") or item.get("new_filename") or item.get("previous_filename") or "").strip()
        if not path:
            continue
        changed_files.append(
            ChangedFile(
                path=path,
                status=str(item.get("status") or "modified"),
                additions=int(item.get("additions") or 0),
                deletions=int(item.get("deletions") or 0),
            )
        )
    if include_paths is not None:
        changed_files = [row for row in changed_files if row.path in include_paths]
        unified = _filter_diff_to_paths(unified, include_paths)

    if not changed_files:
        # keep the snapshot contract valid even if the endpoint is empty.
        changed_files = []

    bounded_files, bounded_diff, bounded_blobs, truncation = _apply_bounds(
        changed_files=changed_files,
        diff_unified=unified,
        context_blobs=[],
        bounds=bounds,
    )

    base_ref = str((pr_payload.get("base") or {}).get("sha") or (pr_payload.get("base") or {}).get("ref") or "")
    head_ref = str((pr_payload.get("head") or {}).get("sha") or (pr_payload.get("head") or {}).get("ref") or "")
    snapshot = ReviewSnapshot(
        source="pr",
        repo={
            "remote": base,
            "repo_id": repo,
            "server_id": str((pr_payload.get("base") or {}).get("repo", {}).get("id") or ""),
        },
        base_ref=base_ref,
        head_ref=head_ref,
        bounds=bounds,
        truncation=truncation,
        changed_files=bounded_files,
        diff_unified=bounded_diff,
        context_blobs=bounded_blobs,
        metadata={
            "title": str(pr_payload.get("title") or ""),
            "author": str((pr_payload.get("user") or {}).get("login") or ""),
            "labels": [str(item.get("name") or "") for item in list(pr_payload.get("labels") or [])],
            **dict(metadata or {}),
        },
    )
    snapshot.compute_snapshot_digest()
    return snapshot


def filter_snapshot_paths(snapshot: ReviewSnapshot, include_paths: set[str]) -> ReviewSnapshot:
    changed_files = [row for row in snapshot.changed_files if row.path in include_paths]
    context_blobs = [blob for blob in snapshot.context_blobs if blob.path in include_paths]
    diff_unified = _filter_diff_to_paths(snapshot.diff_unified, include_paths) if include_paths else ""
    bounded_files, bounded_diff, bounded_blobs, truncation = _apply_bounds(
        changed_files=changed_files,
        diff_unified=diff_unified,
        context_blobs=context_blobs,
        bounds=snapshot.bounds,
    )
    filtered = ReviewSnapshot(
        source=snapshot.source,
        repo=dict(snapshot.repo),
        base_ref=snapshot.base_ref,
        head_ref=snapshot.head_ref,
        bounds=snapshot.bounds,
        truncation=truncation,
        changed_files=bounded_files,
        diff_unified=bounded_diff,
        context_blobs=bounded_blobs,
        metadata=dict(snapshot.metadata),
    )
    filtered.compute_snapshot_digest()
    return filtered
