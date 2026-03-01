from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional


DigestAlgorithm = Literal["sha256"]
ReviewSource = Literal["pr", "diff", "files"]
DeterministicDecision = Literal["pass", "changes_requested", "blocked"]
Severity = Literal["info", "low", "medium", "high", "critical"]


def _normalize_newlines(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _normalize_for_canonical_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _normalize_for_canonical_json(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, list):
        return [_normalize_for_canonical_json(v) for v in value]
    if isinstance(value, str):
        return _normalize_newlines(value)
    return value


def to_canonical_json_bytes(obj: Any) -> bytes:
    normalized = _normalize_for_canonical_json(obj)
    # separators locks whitespace output; ensure_ascii False keeps UTF-8 bytes canonical.
    payload = json.dumps(
        normalized,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return payload.encode("utf-8")


def digest_sha256_prefixed(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


@dataclass(slots=True)
class SnapshotBounds:
    max_files: int = 200
    max_diff_bytes: int = 1_000_000
    max_blob_bytes: int = 200_000
    max_file_bytes: int = 100_000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_files": int(self.max_files),
            "max_diff_bytes": int(self.max_diff_bytes),
            "max_blob_bytes": int(self.max_blob_bytes),
            "max_file_bytes": int(self.max_file_bytes),
        }


@dataclass(slots=True)
class ChangedFile:
    path: str
    status: str
    additions: int
    deletions: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": str(self.path),
            "status": str(self.status),
            "additions": int(self.additions),
            "deletions": int(self.deletions),
        }


@dataclass(slots=True)
class ContextBlob:
    path: str
    content: str
    truncated: bool = False
    omitted_bytes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": str(self.path),
            "content": str(self.content),
            "truncated": bool(self.truncated),
            "omitted_bytes": int(self.omitted_bytes),
        }


@dataclass(slots=True)
class TruncationReport:
    files_truncated: int = 0
    diff_bytes_original: int = 0
    diff_bytes_kept: int = 0
    diff_truncated: bool = False
    blob_bytes_original: int = 0
    blob_bytes_kept: int = 0
    blob_truncated: bool = False
    notes: List[str] | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "files_truncated": int(self.files_truncated),
            "diff_bytes_original": int(self.diff_bytes_original),
            "diff_bytes_kept": int(self.diff_bytes_kept),
            "diff_truncated": bool(self.diff_truncated),
            "blob_bytes_original": int(self.blob_bytes_original),
            "blob_bytes_kept": int(self.blob_bytes_kept),
            "blob_truncated": bool(self.blob_truncated),
            "notes": list(self.notes or []),
        }


@dataclass(slots=True)
class ReviewSnapshot:
    source: ReviewSource
    repo: Dict[str, Any]
    base_ref: str
    head_ref: str
    bounds: SnapshotBounds
    truncation: TruncationReport
    changed_files: List[ChangedFile]
    diff_unified: str
    context_blobs: List[ContextBlob]
    metadata: Dict[str, Any]
    snapshot_digest: str = ""

    def _for_digest(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "repo": dict(self.repo),
            "base_ref": self.base_ref,
            "head_ref": self.head_ref,
            "bounds": self.bounds.to_dict(),
            "truncation": self.truncation.to_dict(),
            "changed_files": [item.to_dict() for item in sorted(self.changed_files, key=lambda row: (row.path, row.status))],
            "diff_unified": self.diff_unified,
            "context_blobs": [blob.to_dict() for blob in self.context_blobs],
            "metadata": dict(self.metadata),
            "snapshot_digest": "",
        }

    def compute_snapshot_digest(self) -> str:
        digest = digest_sha256_prefixed(to_canonical_json_bytes(self._for_digest()))
        self.snapshot_digest = digest
        return digest

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "repo": dict(self.repo),
            "base_ref": self.base_ref,
            "head_ref": self.head_ref,
            "bounds": self.bounds.to_dict(),
            "truncation": self.truncation.to_dict(),
            "changed_files": [item.to_dict() for item in sorted(self.changed_files, key=lambda row: (row.path, row.status))],
            "diff_unified": self.diff_unified,
            "context_blobs": [blob.to_dict() for blob in self.context_blobs],
            "metadata": dict(self.metadata),
            "snapshot_digest": self.snapshot_digest,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ReviewSnapshot":
        bounds_payload = payload.get("bounds") or {}
        trunc_payload = payload.get("truncation") or {}
        changed_files = [
            ChangedFile(
                path=str(item.get("path") or ""),
                status=str(item.get("status") or ""),
                additions=int(item.get("additions") or 0),
                deletions=int(item.get("deletions") or 0),
            )
            for item in list(payload.get("changed_files") or [])
        ]
        context_blobs = [
            ContextBlob(
                path=str(item.get("path") or ""),
                content=str(item.get("content") or ""),
                truncated=bool(item.get("truncated") or False),
                omitted_bytes=int(item.get("omitted_bytes") or 0),
            )
            for item in list(payload.get("context_blobs") or [])
        ]
        snapshot = cls(
            source=str(payload.get("source") or "diff"),  # type: ignore[arg-type]
            repo=dict(payload.get("repo") or {}),
            base_ref=str(payload.get("base_ref") or ""),
            head_ref=str(payload.get("head_ref") or ""),
            bounds=SnapshotBounds(
                max_files=int(bounds_payload.get("max_files") or 200),
                max_diff_bytes=int(bounds_payload.get("max_diff_bytes") or 1_000_000),
                max_blob_bytes=int(bounds_payload.get("max_blob_bytes") or 200_000),
                max_file_bytes=int(bounds_payload.get("max_file_bytes") or 100_000),
            ),
            truncation=TruncationReport(
                files_truncated=int(trunc_payload.get("files_truncated") or 0),
                diff_bytes_original=int(trunc_payload.get("diff_bytes_original") or 0),
                diff_bytes_kept=int(trunc_payload.get("diff_bytes_kept") or 0),
                diff_truncated=bool(trunc_payload.get("diff_truncated") or False),
                blob_bytes_original=int(trunc_payload.get("blob_bytes_original") or 0),
                blob_bytes_kept=int(trunc_payload.get("blob_bytes_kept") or 0),
                blob_truncated=bool(trunc_payload.get("blob_truncated") or False),
                notes=list(trunc_payload.get("notes") or []),
            ),
            changed_files=changed_files,
            diff_unified=str(payload.get("diff_unified") or ""),
            context_blobs=context_blobs,
            metadata=dict(payload.get("metadata") or {}),
            snapshot_digest=str(payload.get("snapshot_digest") or ""),
        )
        if not snapshot.snapshot_digest:
            snapshot.compute_snapshot_digest()
        return snapshot


@dataclass(slots=True)
class DeterministicFinding:
    code: str
    severity: Severity
    message: str
    path: str = ""
    span: Optional[Dict[str, int]] = None
    details: Dict[str, Any] | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "path": self.path,
            "span": dict(self.span or {}),
            "details": dict(self.details or {}),
        }


@dataclass(slots=True)
class DeterministicReviewDecisionPayload:
    decision: DeterministicDecision
    findings: List[DeterministicFinding]
    executed_checks: List[str]
    snapshot_digest: str
    policy_digest: str
    run_id: str
    deterministic_lane_version: str = "deterministic_v0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "findings": [finding.to_dict() for finding in self.findings],
            "executed_checks": list(self.executed_checks),
            "snapshot_digest": self.snapshot_digest,
            "policy_digest": self.policy_digest,
            "run_id": self.run_id,
            "deterministic_lane_version": self.deterministic_lane_version,
        }


@dataclass(slots=True)
class ModelRiskIssue:
    why: str
    where: str
    impact: str
    confidence: float
    suggested_fix: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "why": self.why,
            "where": self.where,
            "impact": self.impact,
            "confidence": float(self.confidence),
            "suggested_fix": self.suggested_fix,
        }


@dataclass(slots=True)
class ModelAssistedCritiquePayload:
    summary: List[str]
    high_risk_issues: List[ModelRiskIssue]
    missing_tests: List[str]
    questions_for_author: List[str]
    nits: List[str]
    refs: List[str]
    model_id: str
    prompt_profile: str
    contract_version: str
    snapshot_digest: str
    policy_digest: str
    run_id: str
    advisory_errors: List[str] | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": list(self.summary),
            "high_risk_issues": [item.to_dict() for item in self.high_risk_issues],
            "missing_tests": list(self.missing_tests),
            "questions_for_author": list(self.questions_for_author),
            "nits": list(self.nits),
            "refs": list(self.refs),
            "model_id": self.model_id,
            "prompt_profile": self.prompt_profile,
            "contract_version": self.contract_version,
            "snapshot_digest": self.snapshot_digest,
            "policy_digest": self.policy_digest,
            "run_id": self.run_id,
            "advisory_errors": list(self.advisory_errors or []),
        }


@dataclass(slots=True)
class ResolvedPolicy:
    payload: Dict[str, Any]
    policy_digest: str

    def to_dict(self) -> Dict[str, Any]:
        return {"policy_digest": self.policy_digest, **dict(self.payload)}


@dataclass(slots=True)
class ReviewRunManifest:
    run_id: str
    snapshot_digest: str
    policy_digest: str
    review_run_contract_version: str
    deterministic_lane_version: str
    bounds: Dict[str, Any]
    truncation: Dict[str, Any]
    auth_source: Literal["token_flag", "token_env", "none"]
    model_lane_contract_version: str = ""
    timings_ms: Dict[str, int] | None = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "run_id": self.run_id,
            "snapshot_digest": self.snapshot_digest,
            "policy_digest": self.policy_digest,
            "review_run_contract_version": self.review_run_contract_version,
            "deterministic_lane_version": self.deterministic_lane_version,
            "bounds": dict(self.bounds),
            "truncation": dict(self.truncation),
            "auth_source": self.auth_source,
            "timings_ms": dict(self.timings_ms or {}),
        }
        if self.model_lane_contract_version:
            payload["model_lane_contract_version"] = self.model_lane_contract_version
        return payload


@dataclass(slots=True)
class ReviewRunResult:
    ok: bool
    run_id: str
    artifact_dir: str
    snapshot_digest: str
    policy_digest: str
    deterministic_decision: DeterministicDecision
    deterministic_findings: int
    model_assisted_enabled: bool
    manifest: Dict[str, Any]
    exit_code: int = 0
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "ok": bool(self.ok),
            "run_id": self.run_id,
            "artifact_dir": self.artifact_dir,
            "snapshot_digest": self.snapshot_digest,
            "policy_digest": self.policy_digest,
            "deterministic_decision": self.deterministic_decision,
            "deterministic_findings": int(self.deterministic_findings),
            "model_assisted_enabled": bool(self.model_assisted_enabled),
            "manifest": dict(self.manifest),
            "exit_code": int(self.exit_code),
        }
        if self.error:
            payload["error"] = self.error
        return payload
