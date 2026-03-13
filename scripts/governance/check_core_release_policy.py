from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger


PYPROJECT_VERSION_RE = re.compile(r'(?m)^version\s*=\s*"([^"]+)"\s*$')
CHANGELOG_VERSION_RE = re.compile(r"(?m)^## \[(\d+\.\d+\.\d+)\]")
TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
ZERO_SHA_RE = re.compile(r"^0+$")


@dataclass(frozen=True, order=True)
class SemVer:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, raw: str) -> "SemVer":
        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", str(raw or "").strip())
        if match is None:
            raise ValueError(f"invalid semantic version: {raw!r}")
        return cls(int(match.group(1)), int(match.group(2)), int(match.group(3)))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate core release version/changelog/tag policy and post-0.4.0 commit discipline.",
    )
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--base-rev", default="", help="Optional base revision for commit-range validation.")
    parser.add_argument("--head-rev", default="HEAD", help="Head revision for commit-range or tag validation.")
    parser.add_argument("--tag", default="", help="Optional core release tag to validate, for example v0.4.0.")
    parser.add_argument(
        "--transition-version",
        default="0.4.0",
        help="Version where commit-based core release discipline becomes active.",
    )
    parser.add_argument("--out", default="", help="Optional JSON output path.")
    return parser


def _run_git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "git command failed: "
            + " ".join(args)
            + f" :: {completed.stderr.strip() or completed.stdout.strip() or f'code={completed.returncode}'}"
        )
    return completed.stdout.strip()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_pyproject_version(text: str) -> str:
    match = PYPROJECT_VERSION_RE.search(text)
    if match is None:
        raise ValueError("pyproject.toml missing [project].version")
    return match.group(1)


def _parse_top_changelog_version(text: str) -> str:
    match = CHANGELOG_VERSION_RE.search(text)
    if match is None:
        raise ValueError("CHANGELOG.md missing top version entry")
    return match.group(1)


def _is_docs_only_path(path_text: str) -> bool:
    normalized = str(path_text or "").strip().replace("\\", "/")
    if not normalized:
        return False
    if normalized.startswith("docs/"):
        return True
    if "/" not in normalized and normalized.endswith(".md"):
        return True
    return False


def _is_docs_only_change(paths: list[str]) -> bool:
    return bool(paths) and all(_is_docs_only_path(path_text) for path_text in paths)


def _load_version_at_ref(repo_root: Path, ref: str) -> str:
    return _parse_pyproject_version(_run_git(repo_root, "show", f"{ref}:pyproject.toml"))


def _load_changelog_version_at_ref(repo_root: Path, ref: str) -> str:
    return _parse_top_changelog_version(_run_git(repo_root, "show", f"{ref}:CHANGELOG.md"))


def _load_head_alignment(repo_root: Path) -> tuple[str, str]:
    pyproject_version = _parse_pyproject_version(_read_text(repo_root / "pyproject.toml"))
    changelog_version = _parse_top_changelog_version(_read_text(repo_root / "CHANGELOG.md"))
    return pyproject_version, changelog_version


def _rev_exists(repo_root: Path, rev: str) -> bool:
    token = str(rev or "").strip()
    if not token or ZERO_SHA_RE.fullmatch(token):
        return False
    completed = subprocess.run(
        ["git", "rev-parse", "--verify", token],
        cwd=str(repo_root),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.returncode == 0


def _commit_parent(repo_root: Path, commit: str) -> str:
    output = _run_git(repo_root, "rev-list", "--parents", "-n", "1", commit)
    parts = [part for part in output.split() if part]
    if len(parts) < 2:
        return ""
    return parts[1]


def _changed_paths_for_commit(repo_root: Path, parent: str, commit: str) -> list[str]:
    output = _run_git(repo_root, "diff", "--name-only", parent, commit)
    return [line.strip() for line in output.splitlines() if line.strip()]


def _version_step_allowed(previous: SemVer, current: SemVer) -> bool:
    if current.major == previous.major and current.minor == previous.minor and current.patch == previous.patch + 1:
        return True
    if current.major == previous.major and current.minor == previous.minor + 1 and current.patch == 0:
        return True
    if current.major == previous.major + 1 and current.minor == 0 and current.patch == 0:
        return True
    return False


def _transition_active(previous: SemVer, current: SemVer, transition: SemVer) -> bool:
    return previous >= transition or current >= transition


def _proof_report_exists_at_ref(repo_root: Path, ref: str, version: str) -> bool:
    proof_path = f"docs/releases/{version}/PROOF_REPORT.md"
    completed = subprocess.run(
        ["git", "cat-file", "-e", f"{ref}:{proof_path}"],
        cwd=str(repo_root),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.returncode == 0


def _tag_is_annotated(repo_root: Path, tag: str) -> bool:
    completed = subprocess.run(
        ["git", "cat-file", "-t", f"refs/tags/{tag}"],
        cwd=str(repo_root),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RuntimeError(f"missing tag ref: {tag}")
    return completed.stdout.strip() == "tag"


def _append_assertion(assertions: list[dict[str, Any]], *, assertion_id: str, passed: bool, detail: str) -> None:
    assertions.append({"id": assertion_id, "passed": passed, "detail": detail})


def _check_head_alignment(repo_root: Path, assertions: list[dict[str, Any]], failures: list[str]) -> str:
    pyproject_version, changelog_version = _load_head_alignment(repo_root)
    passed = pyproject_version == changelog_version
    detail = f"pyproject={pyproject_version} changelog={changelog_version}"
    _append_assertion(assertions, assertion_id="head_version_matches_changelog", passed=passed, detail=detail)
    if not passed:
        failures.append(f"head version drift: pyproject.toml={pyproject_version} CHANGELOG.md={changelog_version}")
    return pyproject_version


def _check_commit_range(
    repo_root: Path,
    *,
    base_rev: str,
    head_rev: str,
    transition: SemVer,
    assertions: list[dict[str, Any]],
    failures: list[str],
) -> None:
    base_token = str(base_rev or "").strip()
    if not _rev_exists(repo_root, base_token):
        _append_assertion(
            assertions,
            assertion_id="commit_range_check",
            passed=True,
            detail=f"skipped base_rev={base_token or '<empty>'}",
        )
        return

    commits_output = _run_git(repo_root, "rev-list", "--reverse", f"{base_token}..{head_rev}")
    commits = [line.strip() for line in commits_output.splitlines() if line.strip()]
    if not commits:
        _append_assertion(
            assertions,
            assertion_id="commit_range_check",
            passed=True,
            detail=f"no commits in range {base_token}..{head_rev}",
        )
        return

    range_passed = True
    checked_commits = 0
    exempt_commits = 0
    skipped_pre_transition = 0
    for commit in commits:
        parent = _commit_parent(repo_root, commit)
        if not parent:
            continue
        paths = _changed_paths_for_commit(repo_root, parent, commit)
        if _is_docs_only_change(paths):
            exempt_commits += 1
            continue

        previous_version = SemVer.parse(_load_version_at_ref(repo_root, parent))
        current_version = SemVer.parse(_load_version_at_ref(repo_root, commit))
        if not _transition_active(previous_version, current_version, transition):
            skipped_pre_transition += 1
            continue

        checked_commits += 1
        changelog_version = _load_changelog_version_at_ref(repo_root, commit)
        version_step_ok = _version_step_allowed(previous_version, current_version)
        changelog_ok = changelog_version == str(current_version)
        commit_passed = version_step_ok and changelog_ok
        range_passed = range_passed and commit_passed
        detail = (
            f"commit={commit} previous={previous_version} current={current_version} "
            f"changelog={changelog_version} paths={paths}"
        )
        _append_assertion(
            assertions,
            assertion_id=f"commit_{commit[:12]}_release_step",
            passed=commit_passed,
            detail=detail,
        )
        if not version_step_ok:
            failures.append(
                f"non-exempt commit {commit[:12]} does not advance version correctly: "
                f"previous={previous_version} current={current_version}"
            )
        if not changelog_ok:
            failures.append(
                f"non-exempt commit {commit[:12]} has changelog drift: "
                f"version={current_version} changelog={changelog_version}"
            )

    summary_detail = (
        f"range={base_token}..{head_rev} commits={len(commits)} "
        f"checked={checked_commits} exempt={exempt_commits} pre_transition_skipped={skipped_pre_transition}"
    )
    _append_assertion(assertions, assertion_id="commit_range_summary", passed=range_passed, detail=summary_detail)


def _check_tag(
    repo_root: Path,
    *,
    tag: str,
    transition: SemVer,
    assertions: list[dict[str, Any]],
    failures: list[str],
) -> None:
    tag_token = str(tag or "").strip()
    if not tag_token:
        return

    format_ok = TAG_RE.fullmatch(tag_token) is not None
    _append_assertion(
        assertions,
        assertion_id="tag_format_is_canonical",
        passed=format_ok,
        detail=f"tag={tag_token}",
    )
    if not format_ok:
        failures.append(f"core release tag must use v<major>.<minor>.<patch>: {tag_token}")
        return

    annotated = _tag_is_annotated(repo_root, tag_token)
    _append_assertion(
        assertions,
        assertion_id="tag_is_annotated",
        passed=annotated,
        detail=f"tag={tag_token} annotated={annotated}",
    )
    if not annotated:
        failures.append(f"core release tag is not annotated: {tag_token}")

    commit_ref = f"{tag_token}^{{commit}}"
    version = _load_version_at_ref(repo_root, commit_ref)
    changelog_version = _load_changelog_version_at_ref(repo_root, commit_ref)
    expected_tag = f"v{version}"
    tag_matches_version = tag_token == expected_tag
    changelog_matches_version = changelog_version == version
    _append_assertion(
        assertions,
        assertion_id="tag_matches_core_version",
        passed=tag_matches_version,
        detail=f"tag={tag_token} expected={expected_tag}",
    )
    _append_assertion(
        assertions,
        assertion_id="tag_commit_changelog_matches_version",
        passed=changelog_matches_version,
        detail=f"tag={tag_token} version={version} changelog={changelog_version}",
    )
    if not tag_matches_version:
        failures.append(f"tag/version mismatch: tag={tag_token} expected={expected_tag}")
    if not changelog_matches_version:
        failures.append(f"tag/changelog mismatch: tag={tag_token} version={version} changelog={changelog_version}")

    parsed_version = SemVer.parse(version)
    if parsed_version >= transition and parsed_version.patch == 0:
        has_proof_report = _proof_report_exists_at_ref(repo_root, commit_ref, version)
        _append_assertion(
            assertions,
            assertion_id="minor_release_has_proof_report",
            passed=has_proof_report,
            detail=f"tag={tag_token} proof_report=docs/releases/{version}/PROOF_REPORT.md",
        )
        if not has_proof_report:
            failures.append(f"missing minor-release proof report for {tag_token}: docs/releases/{version}/PROOF_REPORT.md")


def _build_payload(
    *,
    repo_root: Path,
    assertions: list[dict[str, Any]],
    failures: list[str],
    base_rev: str,
    head_rev: str,
    tag: str,
    transition_version: str,
) -> dict[str, Any]:
    return {
        "schema_version": "governance.core_release_policy.v1",
        "status": "PASS" if not failures and all(bool(row.get("passed")) for row in assertions) else "FAIL",
        "repo_root": repo_root.resolve().as_posix(),
        "base_rev": str(base_rev or "").strip(),
        "head_rev": str(head_rev or "").strip(),
        "tag": str(tag or "").strip(),
        "transition_version": transition_version,
        "assertions": assertions,
        "failures": failures,
    }


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo_root = Path(str(args.repo_root)).resolve()
    transition = SemVer.parse(str(args.transition_version))

    assertions: list[dict[str, Any]] = []
    failures: list[str] = []

    _check_head_alignment(repo_root, assertions, failures)
    _check_commit_range(
        repo_root,
        base_rev=str(args.base_rev),
        head_rev=str(args.head_rev),
        transition=transition,
        assertions=assertions,
        failures=failures,
    )
    _check_tag(
        repo_root,
        tag=str(args.tag),
        transition=transition,
        assertions=assertions,
        failures=failures,
    )

    payload = _build_payload(
        repo_root=repo_root,
        assertions=assertions,
        failures=failures,
        base_rev=str(args.base_rev),
        head_rev=str(args.head_rev),
        tag=str(args.tag),
        transition_version=str(transition),
    )

    out_path = str(args.out or "").strip()
    if out_path:
        write_payload_with_diff_ledger(Path(out_path), payload)

    if payload["status"] == "PASS":
        print("Core release policy check passed.")
        return 0

    print("Core release policy check failed:")
    for failure in failures:
        print(f"- {failure}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
