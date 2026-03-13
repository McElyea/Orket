from __future__ import annotations

import argparse
import asyncio
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


LOCAL_TIMEZONE = ZoneInfo("America/Denver")
TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
PYPROJECT_VERSION_RE = re.compile(rb'(?m)^version\s*=\s*"([^"]+)"\s*$')
CHANGELOG_ENTRY_RE = re.compile(rb"(?m)^## \[(\d+\.\d+\.\d+)\]")
CHANGELOG_SECTION_RE_TEMPLATE = r"(?ms)^## \[{version}\].*?(?=^## \[\d+\.\d+\.\d+\]|\Z)"
PROOF_PLACEHOLDER_RE = re.compile(r"<[^>\n]+>")
PENDING_RELEASE_NOTES_LINE = "- Pending release notes."


@dataclass(frozen=True)
class ReleaseTarget:
    tag: str
    version: str
    major: int
    minor: int
    patch: int


@dataclass(frozen=True)
class GitResult:
    returncode: int
    stdout: str
    stderr: str


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare canonical core release files from a core release tag and optionally create the tag.",
    )
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--tag", required=True, help="Core release tag, for example v0.4.0.")
    parser.add_argument("--title", default="Pending Release", help="Release title used when creating a changelog entry.")
    parser.add_argument(
        "--date",
        default="",
        help="Release date in YYYY-MM-DD format. Defaults to the local America/Denver date.",
    )
    parser.add_argument(
        "--commit-and-tag",
        action="store_true",
        help="Stage canonical files, commit them if changed, and create the annotated tag.",
    )
    parser.add_argument(
        "--commit-message",
        default="",
        help="Optional commit message override when --commit-and-tag is used.",
    )
    parser.add_argument(
        "--tag-message",
        default="",
        help="Optional annotated tag message override when --commit-and-tag is used.",
    )
    return parser


def _read_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("utf-8"))


def _resolve_date(raw: str) -> str:
    value = str(raw or "").strip()
    if value:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    return datetime.now(LOCAL_TIMEZONE).date().isoformat()


def _parse_target(raw_tag: str) -> ReleaseTarget:
    token = str(raw_tag or "").strip()
    match = TAG_RE.fullmatch(token)
    if match is None:
        raise ValueError(f"invalid core release tag: {token!r}")
    version = f"{match.group(1)}.{match.group(2)}.{match.group(3)}"
    return ReleaseTarget(
        tag=token,
        version=version,
        major=int(match.group(1)),
        minor=int(match.group(2)),
        patch=int(match.group(3)),
    )


def _replace_pyproject_version(text: str, version: str) -> tuple[str, bool]:
    raw = text.encode("utf-8")
    if PYPROJECT_VERSION_RE.search(raw) is None:
        raise ValueError("pyproject.toml missing [project].version")
    replaced = PYPROJECT_VERSION_RE.sub(f'version = "{version}"'.encode("utf-8"), raw, count=1)
    updated = replaced.decode("utf-8")
    return updated, updated != text


def _release_block(version: str, date_text: str, title: str) -> str:
    clean_title = str(title or "").strip() or "Pending Release"
    return (
        f'## [{version}] - {date_text} - "{clean_title}"\n\n'
        "### Changed\n"
        "- Pending release notes.\n\n"
    )


def _ensure_changelog_entry(text: str, *, version: str, date_text: str, title: str) -> tuple[str, bool]:
    raw = text.encode("utf-8")
    match = CHANGELOG_ENTRY_RE.search(raw)
    if match is not None and match.group(1).decode("utf-8") == version:
        return text, False

    block = _release_block(version, date_text, title)
    if match is None:
        separator = "" if text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
        updated = f"{text}{separator}{block}"
        return updated, True

    insertion_index = match.start()
    updated = text[:insertion_index] + block + text[insertion_index:]
    return updated, True


def _extract_changelog_entry(text: str, version: str) -> str:
    pattern = re.compile(CHANGELOG_SECTION_RE_TEMPLATE.format(version=re.escape(version)))
    match = pattern.search(text)
    if match is None:
        raise ValueError(f"CHANGELOG.md missing entry for {version}")
    return match.group(0)


def _changelog_entry_release_ready(text: str, version: str) -> tuple[bool, list[str]]:
    issues: list[str] = []
    entry = _extract_changelog_entry(text, version)
    if PENDING_RELEASE_NOTES_LINE in entry:
        issues.append("CHANGELOG.md still contains placeholder release notes")
    return not issues, issues


def _proof_report_text(target: ReleaseTarget, date_text: str) -> str:
    return (
        f"# Release `{target.version}` Proof Report\n\n"
        f"Date: `{date_text}`\n"
        "Owner: `Orket Core`\n"
        f"Git tag: `{target.tag}`\n"
        "Completed major project: `<roadmap lane or closeout reference>`\n"
        "Release policy authority: [docs/specs/CORE_RELEASE_VERSIONING_POLICY.md](docs/specs/CORE_RELEASE_VERSIONING_POLICY.md)\n"
        "Release gate checklist: [docs/specs/CORE_RELEASE_GATE_CHECKLIST.md](docs/specs/CORE_RELEASE_GATE_CHECKLIST.md)\n\n"
        "## Summary of Change\n\n"
        "<Pending summary.>\n\n"
        "## Stability Statement\n\n"
        "<Pending stability statement.>\n\n"
        "## Compatibility Classification\n\n"
        "- `compatibility_status`: `<preserved|breaking|deprecated>`\n"
        "- `affected_audience`: `<operator_only|extension_author_only|internal_only|all>`\n"
        "- `migration_requirement`: `<none|required>`\n\n"
        "## Required Operator or Extension-Author Action\n\n"
        "None.\n\n"
        "## Proof Record Index\n\n"
        "| Surface | Surface Type | Proof Mode | Proof Result | Reason | Evidence |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| `<surface name>` | `<default_runtime_entrypoint|api_runtime_entrypoint|workflow_path|integration_route>` | `<live|structural>` | `<success|blocked|not_applicable>` | `<reason or none>` | `<repo-relative links>` |\n\n"
        "## Detailed Proof Records\n\n"
        "### `<surface name>`\n\n"
        "- `surface_type`: `<default_runtime_entrypoint|api_runtime_entrypoint|workflow_path|integration_route>`\n"
        "- `proof_mode`: `<live|structural>`\n"
        "- `proof_result`: `<success|blocked|not_applicable>`\n"
        "- `reason`: `<required when proof_mode is structural or proof_result is blocked/not_applicable; otherwise none>`\n"
        "- `evidence`: `<repo-relative links to logs, screenshots, traces, command transcripts, or narrative evidence>`\n"
        "- `notes`: `<optional>`\n"
    )


def _ensure_proof_report(repo_root: Path, target: ReleaseTarget, date_text: str) -> tuple[Path | None, bool]:
    if target.patch != 0:
        return None, False
    proof_path = repo_root / "docs" / "releases" / target.version / "PROOF_REPORT.md"
    if proof_path.exists():
        return proof_path, False
    _write_text(proof_path, _proof_report_text(target, date_text))
    return proof_path, True


def _proof_report_release_ready(path: Path) -> tuple[bool, list[str]]:
    issues: list[str] = []
    text = _read_text(path)
    if PROOF_PLACEHOLDER_RE.search(text) is not None:
        issues.append(f"{path.as_posix()} still contains unresolved template placeholders")
    return not issues, issues


async def _run_git(repo_root: Path, *args: str) -> GitResult:
    process = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=str(repo_root),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = await process.communicate()
    return GitResult(
        returncode=int(process.returncode or 0),
        stdout=stdout_bytes.decode("utf-8", errors="replace"),
        stderr=stderr_bytes.decode("utf-8", errors="replace"),
    )


async def _git_add(repo_root: Path, paths: list[str]) -> None:
    result = await _run_git(repo_root, "add", "--", *paths)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git add failed")


async def _git_name_only(repo_root: Path, *args: str) -> list[str]:
    result = await _run_git(repo_root, *args)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git path query failed")
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


async def _git_has_staged_changes(repo_root: Path) -> bool:
    result = await _run_git(repo_root, "diff", "--cached", "--quiet")
    if result.returncode == 0:
        return False
    if result.returncode == 1:
        return True
    raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git diff --cached failed")


async def _git_commit(repo_root: Path, message: str) -> None:
    result = await _run_git(repo_root, "commit", "-m", message)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git commit failed")


async def _git_tag(repo_root: Path, tag: str, message: str) -> None:
    result = await _run_git(repo_root, "tag", "-a", tag, "-m", message)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git tag failed")


async def _git_tag_exists(repo_root: Path, tag: str) -> bool:
    result = await _run_git(repo_root, "rev-parse", "--verify", f"refs/tags/{tag}")
    if result.returncode == 0:
        return True
    if result.returncode == 128:
        return False
    raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git rev-parse tag check failed")


async def _git_preexisting_dirty_paths(repo_root: Path) -> set[str]:
    staged = await _git_name_only(repo_root, "diff", "--cached", "--name-only")
    unstaged = await _git_name_only(repo_root, "diff", "--name-only")
    untracked = await _git_name_only(repo_root, "ls-files", "--others", "--exclude-standard")
    return {path for path in [*staged, *unstaged, *untracked] if path}


async def _async_main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo_root = Path(str(args.repo_root)).resolve()
    target = _parse_target(str(args.tag))
    date_text = _resolve_date(str(args.date))

    pyproject_path = repo_root / "pyproject.toml"
    changelog_path = repo_root / "CHANGELOG.md"
    proof_path = repo_root / "docs" / "releases" / target.version / "PROOF_REPORT.md"
    tracked_release_paths = {
        pyproject_path.relative_to(repo_root).as_posix(),
        changelog_path.relative_to(repo_root).as_posix(),
    }
    if target.patch == 0:
        tracked_release_paths.add(proof_path.relative_to(repo_root).as_posix())

    if args.commit_and_tag:
        if await _git_tag_exists(repo_root, target.tag):
            raise RuntimeError(f"tag already exists: {target.tag}")
        dirty_paths = await _git_preexisting_dirty_paths(repo_root)
        unrelated_paths = sorted(path for path in dirty_paths if path not in tracked_release_paths)
        if unrelated_paths:
            joined = ", ".join(unrelated_paths)
            raise RuntimeError(f"release prep requires a clean worktree outside canonical release files: {joined}")

    pyproject_text = _read_text(pyproject_path)
    updated_pyproject, pyproject_changed = _replace_pyproject_version(pyproject_text, target.version)
    if pyproject_changed:
        _write_text(pyproject_path, updated_pyproject)

    changelog_text = _read_text(changelog_path)
    updated_changelog, changelog_changed = _ensure_changelog_entry(
        changelog_text,
        version=target.version,
        date_text=date_text,
        title=str(args.title),
    )
    if changelog_changed:
        _write_text(changelog_path, updated_changelog)

    ensured_proof_path, proof_created = _ensure_proof_report(repo_root, target, date_text)

    if args.commit_and_tag:
        changelog_ready, changelog_issues = _changelog_entry_release_ready(_read_text(changelog_path), target.version)
        release_issues = list(changelog_issues)
        if ensured_proof_path is not None:
            proof_ready, proof_issues = _proof_report_release_ready(ensured_proof_path)
            if not proof_ready:
                release_issues.extend(proof_issues)
        if not changelog_ready or release_issues:
            raise RuntimeError("; ".join(release_issues))

        tracked_paths = ["pyproject.toml", "CHANGELOG.md"]
        if ensured_proof_path is not None:
            tracked_paths.append(ensured_proof_path.relative_to(repo_root).as_posix())
        await _git_add(repo_root, tracked_paths)

        if await _git_has_staged_changes(repo_root):
            commit_message = str(args.commit_message).strip() or f"Prepare core release {target.tag}"
            await _git_commit(repo_root, commit_message)

        tag_message = str(args.tag_message).strip() or f"Core release {target.tag}"
        await _git_tag(repo_root, target.tag, tag_message)

    print(f"Prepared core release {target.tag}")
    print(f"- pyproject version: {target.version} (changed={pyproject_changed})")
    print(f"- changelog entry: {target.version} (changed={changelog_changed})")
    if ensured_proof_path is not None:
        print(f"- proof report: {ensured_proof_path.relative_to(repo_root).as_posix()} (created={proof_created})")
    if args.commit_and_tag:
        print("- commit/tag: created")
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return asyncio.run(_async_main(argv))
    except Exception as exc:  # pragma: no cover - CLI boundary
        print(f"E_PREPARE_CORE_RELEASE_FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
