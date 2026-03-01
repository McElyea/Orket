from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List

from orket.application.review.models import (
    DeterministicFinding,
    DeterministicReviewDecisionPayload,
    ReviewSnapshot,
)


SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


def _stable_sort_findings(findings: List[DeterministicFinding]) -> List[DeterministicFinding]:
    def key(item: DeterministicFinding) -> tuple[Any, ...]:
        path_key = item.path if item.path else "\uffff"
        span_start = int((item.span or {}).get("start") or 0)
        msg_digest = hashlib.sha256(item.message.encode("utf-8")).hexdigest()
        return (
            -SEVERITY_RANK.get(item.severity, 0),
            item.code,
            path_key,
            span_start,
            msg_digest,
        )

    return sorted(findings, key=key)


def run_deterministic_lane(
    *,
    snapshot: ReviewSnapshot,
    resolved_policy: Dict[str, Any],
    run_id: str,
    policy_digest: str,
) -> DeterministicReviewDecisionPayload:
    checks = ((resolved_policy.get("deterministic") or {}).get("checks") or {})
    findings: List[DeterministicFinding] = []
    executed_checks: List[str] = []

    blocked_prefixes = [str(item) for item in list(checks.get("path_blocklist") or [])]
    if blocked_prefixes:
        executed_checks.append("path_policy")
        for changed in snapshot.changed_files:
            if not changed.path:
                continue
            for prefix in blocked_prefixes:
                if changed.path.startswith(prefix):
                    findings.append(
                        DeterministicFinding(
                            code="PATH_BLOCKED",
                            severity="high",
                            message=f"Path '{changed.path}' is blocked by policy prefix '{prefix}'",
                            path=changed.path,
                            details={"prefix": prefix},
                        )
                    )

    patterns = [str(item) for item in list(checks.get("forbidden_patterns") or [])]
    if patterns:
        executed_checks.append("forbidden_patterns")
        for pattern in patterns:
            try:
                regex = re.compile(pattern, re.MULTILINE)
            except re.error:
                findings.append(
                    DeterministicFinding(
                        code="PATTERN_INVALID",
                        severity="medium",
                        message=f"Invalid forbidden pattern in policy: {pattern}",
                        details={"pattern": pattern},
                    )
                )
                continue
            if regex.search(snapshot.diff_unified):
                findings.append(
                    DeterministicFinding(
                        code="PATTERN_MATCHED",
                        severity="high",
                        message=f"Forbidden pattern matched: {pattern}",
                        details={"pattern": pattern},
                    )
                )

    executed_checks.append("thresholds")
    if snapshot.truncation.files_truncated > 0:
        findings.append(
            DeterministicFinding(
                code="FILES_TRUNCATED",
                severity="high",
                message="Changed files exceeded policy max_files and were truncated.",
                details={"files_truncated": snapshot.truncation.files_truncated},
            )
        )
    if snapshot.truncation.diff_truncated:
        findings.append(
            DeterministicFinding(
                code="DIFF_TRUNCATED",
                severity="high",
                message="Diff exceeded policy max_diff_bytes and was truncated.",
                details={
                    "original": snapshot.truncation.diff_bytes_original,
                    "kept": snapshot.truncation.diff_bytes_kept,
                },
            )
        )

    executed_checks.append("test_hints")
    required_roots = [str(item) for item in list(checks.get("test_hint_required_roots") or [])]
    test_roots = [str(item) for item in list(checks.get("test_hint_test_roots") or [])]
    src_changed = any(any(changed.path.startswith(root) for root in required_roots) for changed in snapshot.changed_files)
    tests_changed = any(any(changed.path.startswith(root) for root in test_roots) for changed in snapshot.changed_files)
    if src_changed and not tests_changed:
        findings.append(
            DeterministicFinding(
                code="TEST_HINT_MISSING",
                severity="low",
                message="Source changes detected without corresponding test path changes.",
            )
        )

    findings = _stable_sort_findings(findings)
    if any(item.severity == "critical" for item in findings):
        decision = "blocked"
    elif any(item.severity in {"high", "medium"} for item in findings):
        decision = "changes_requested"
    else:
        decision = "pass"

    return DeterministicReviewDecisionPayload(
        decision=decision,
        findings=findings,
        executed_checks=executed_checks,
        snapshot_digest=snapshot.snapshot_digest,
        policy_digest=policy_digest,
        run_id=run_id,
    )

