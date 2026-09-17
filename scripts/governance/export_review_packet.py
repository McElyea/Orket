"""Export a bounded review copy from the shared Git inventory; CLI tooling only."""

from __future__ import annotations

import argparse
from fnmatch import fnmatch
from pathlib import Path

from scripts.common.git_inventory import GitInventoryError, git_list_files

DEFAULT_OUTPUT_FILE = "Agents/review/project_review_packet.txt"
TEXT_SUFFIXES = frozenset({
    ".py", ".pyi", ".pyx", ".pxd", ".bat", ".cfg", ".conf", ".css", ".csv", ".html",
    ".ini", ".in", ".js", ".json", ".jsx", ".md", ".ps1", ".scss", ".sh", ".sql",
    ".svg", ".toml", ".ts", ".tsx", ".txt", ".yaml", ".yml",
})
SPECIAL_NAMES = frozenset({
    ".coveragerc", ".editorconfig", ".flake8", ".gitattributes", ".gitignore", ".gitmodules",
    ".python-version", ".tool-versions", "Containerfile", "Dockerfile", "MANIFEST.in", "Makefile", "py.typed",
})
SPECIAL_PATTERNS = ("Dockerfile.*", "*.env.example", "*.env.sample", "*.env.template")
SECRET_PATTERNS = (".env", ".env.*", "*.pem", "*.key", "*.crt", "*.p12")
SKIP_DIRS = frozenset({
    ".git", ".venv", "venv", "env", "node_modules", "__pycache__", "build", "dist", "backups",
    ".idea", ".vscode", ".mypy_cache", ".nox", ".pytest_cache", ".ruff_cache", ".tmp", ".tox",
    "_review_stage", "_upload_packets", "basetemp", "downloads", "eggs", "logs", "orket_storage",
    "parts", "pytest-of-jonmc", "pytest-temp", "pytest_tmp", "results", "sandbox_pytest", "sdist",
    "tmp", "tmp_codex_pytest", "tmp_tests", "wheels",
})
LOCKFILES = frozenset({"package-lock.json", "Pipfile.lock", "poetry.lock", "uv.lock"})


def _included(path: Path, root: Path, output: Path, *, include_patch: bool, include_lockfiles: bool) -> bool:
    if path.resolve() == output or any(part in SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
        return False
    if any(fnmatch(path.name, pattern) for pattern in SECRET_PATTERNS):
        return False
    if path.name in LOCKFILES:
        return include_lockfiles
    if path.name == "review-working-tree.patch":
        return include_patch
    if fnmatch(path.name, "project_dump*.txt"):
        return False
    return (path.suffix.lower() in TEXT_SUFFIXES or path.name in SPECIAL_NAMES
            or any(fnmatch(path.name, pattern) for pattern in SPECIAL_PATTERNS))


def _entry(path: Path, root: Path, max_file_size: int) -> tuple[str, bool]:
    with path.open("rb") as handle:
        data = handle.read(max_file_size + 1)
    omitted = len(data) > max_file_size or b"\0" in data
    if len(data) > max_file_size:
        content = "[Omitted: file exceeds byte limit]"
    elif b"\0" in data:
        content = "[Omitted: binary content]"
    else:
        content = data.decode("utf-8")
    return f'<file path="{path.relative_to(root).as_posix()}">\n{content}\n</file>', omitted


def export_project_review_packet(
    root_dir: str = ".", output_file: str = DEFAULT_OUTPUT_FILE, *,
    max_file_size: int = 200_000, max_total_chars: int = 3_500_000,
    include_patch: bool = False, include_lockfiles: bool = False,
) -> bool:
    """Write a filtered review packet; return False when eligible content was omitted."""
    if max_file_size < 1 or max_total_chars < 256:
        raise ValueError("File limit must be positive and total character limit must be at least 256")
    root = Path(root_dir).resolve(strict=True)
    output = (root / output_file).resolve()
    files = git_list_files(root)
    entries, total, complete = [], 0, True
    # Reserve space for the mandatory scope/result header, including on a capped export.
    for path in files:
        if not _included(path, root, output, include_patch=include_patch, include_lockfiles=include_lockfiles):
            continue
        entry, omitted = _entry(path, root, max_file_size)
        if total + len(entry) + 2 > max_total_chars - 256:
            complete = False
            break
        entries.append(entry)
        total += len(entry) + 2
        complete = complete and not omitted
    header = ("Scope: filtered Git-visible source/config review copy; not authoritative runtime evidence.\n"
              f"Result: {'complete within filter' if complete else 'partial; eligible content omitted'}\n")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(header + "\n\n".join(entries), encoding="utf-8")
    return complete


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_FILE)
    parser.add_argument("--max-file-size", type=int, default=200_000)
    parser.add_argument("--max-total-chars", type=int, default=3_500_000)
    parser.add_argument("--include-patch", action="store_true")
    parser.add_argument("--include-lockfiles", action="store_true")
    args = parser.parse_args(argv)
    try:
        complete = export_project_review_packet(
            args.root, args.output, max_file_size=args.max_file_size, max_total_chars=args.max_total_chars,
            include_patch=args.include_patch, include_lockfiles=args.include_lockfiles,
        )
    except (OSError, UnicodeError, ValueError, GitInventoryError) as exc:
        parser.exit(1, f"Review packet failed: {exc}\n")
    print(f"Review packet {'written within filter' if complete else 'partial'}: {args.output}")
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
