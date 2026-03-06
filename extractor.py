from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

INCLUDE_SUFFIXES = {
    ".py",
    ".md",
    ".toml",
    ".json",
    ".yml",
    ".yaml",
    ".ini",
}

EXCLUDE_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
}

STAGE_DIR_NAME = "_review_stage"
ZIP_NAME = "orket-review-packet.zip"

GIT_STATUS_NAME = "review-git-status.txt"
GIT_HEAD_NAME = "review-git-head.txt"
GIT_DIFFSTAT_NAME = "review-git-diffstat.txt"
GIT_PATCH_NAME = "review-working-tree.patch"


def is_excluded(path: Path) -> bool:
    return any(part in EXCLUDE_DIR_NAMES for part in path.parts)


def collect_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if is_excluded(path.relative_to(repo_root)):
            continue
        if path.suffix.lower() in INCLUDE_SUFFIXES:
            files.append(path)
    return files


def reset_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def stage_files(repo_root: Path, stage_dir: Path, files: list[Path]) -> None:
    for source in files:
        relative = source.relative_to(repo_root)
        target = stage_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def write_zip_from_stage(stage_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in stage_dir.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(stage_dir)
                zf.write(file_path, arcname)


def run_git_command(repo_root: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return "git executable not found\n"

    if result.returncode != 0 and not result.stdout and result.stderr:
        return result.stderr
    return result.stdout


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def write_git_artifacts(repo_root: Path) -> None:
    write_text(repo_root / GIT_STATUS_NAME, run_git_command(repo_root, ["status", "--short"]))
    write_text(repo_root / GIT_HEAD_NAME, run_git_command(repo_root, ["rev-parse", "HEAD"]))
    write_text(repo_root / GIT_DIFFSTAT_NAME, run_git_command(repo_root, ["diff", "--stat"]))
    write_text(repo_root / GIT_PATCH_NAME, run_git_command(repo_root, ["diff"]))


def main() -> int:
    repo_root = Path.cwd()
    stage_dir = repo_root / STAGE_DIR_NAME
    zip_path = repo_root / ZIP_NAME

    print(f"Repo root: {repo_root}")
    print("Collecting files...")

    files = collect_files(repo_root)
    print(f"Found {len(files)} files to include.")

    reset_path(stage_dir)
    reset_path(zip_path)

    print("Staging files...")
    stage_dir.mkdir(parents=True, exist_ok=True)
    stage_files(repo_root, stage_dir, files)

    print(f"Creating zip: {zip_path.name}")
    write_zip_from_stage(stage_dir, zip_path)

    print("Writing git review artifacts...")
    write_git_artifacts(repo_root)

    print("Cleaning up staging directory...")
    reset_path(stage_dir)

    print("Done.")
    print(f"Created: {zip_path.name}")
    print(f"Created: {GIT_STATUS_NAME}")
    print(f"Created: {GIT_HEAD_NAME}")
    print(f"Created: {GIT_DIFFSTAT_NAME}")
    print(f"Created: {GIT_PATCH_NAME}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())