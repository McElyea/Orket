#!/usr/bin/env python3
"""Stamp a package version using UTC CalVer + git commit count."""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
from pathlib import Path


def _git_commit_count(path: str) -> int:
    proc = subprocess.run(
        ["git", "rev-list", "--count", "HEAD", "--", path],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to compute commit count for {path}: {proc.stderr.strip()}")
    raw = proc.stdout.strip()
    return int(raw or "0")


def _calver_version(package_path: str) -> str:
    today = dt.datetime.now(dt.UTC).strftime("%Y.%m.%d")
    count = _git_commit_count(package_path)
    return f"{today}.dev{count}"


def _replace_project_version(pyproject_text: str, new_version: str) -> str:
    section_pattern = re.compile(r"(?ms)^\[project\]\n(.*?)(?:^\[|\Z)")
    match = section_pattern.search(pyproject_text)
    if not match:
        raise ValueError("No [project] section found in pyproject.toml")

    section = match.group(1)
    version_pattern = re.compile(r'(?m)^version\s*=\s*"[^"]*"\s*$')
    if not version_pattern.search(section):
        raise ValueError("No project version field found in [project] section")

    updated_section = version_pattern.sub(f'version = "{new_version}"', section, count=1)
    start = match.start(1)
    end = match.end(1)
    return pyproject_text[:start] + updated_section + pyproject_text[end:]


def main() -> None:
    parser = argparse.ArgumentParser(description="Stamp pyproject version with CalVer.")
    parser.add_argument("--pyproject", required=True, help="Path to package pyproject.toml")
    parser.add_argument("--package-path", required=True, help="Path scope used for git commit count")
    parser.add_argument("--dry-run", action="store_true", help="Print version without writing file")
    args = parser.parse_args()

    pyproject_path = Path(args.pyproject)
    if not pyproject_path.exists():
        raise SystemExit(f"File not found: {pyproject_path}")

    new_version = _calver_version(args.package_path)
    if args.dry_run:
        print(new_version)
        return

    original = pyproject_path.read_text(encoding="utf-8")
    updated = _replace_project_version(original, new_version)
    pyproject_path.write_text(updated, encoding="utf-8")
    print(new_version)


if __name__ == "__main__":
    main()
