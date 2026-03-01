#!/usr/bin/env python3
"""Stamp CalVer versions for packages touched in the staged diff."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def _run(args: list[str]) -> str:
    proc = subprocess.run(args, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _staged_files() -> list[str]:
    out = _run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"])
    return [line.strip().replace("\\", "/") for line in out.splitlines() if line.strip()]


def _under(path: str, prefix: str) -> bool:
    norm = prefix.strip("/").replace("\\", "/")
    return path == norm or path.startswith(f"{norm}/")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stamp versions for changed packages.")
    parser.add_argument("--config", default=".ci/packages.json", help="Path to package config JSON")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        raise SystemExit(f"Config file not found: {config_path}")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    packages = config.get("packages", [])
    if not isinstance(packages, list):
        raise SystemExit("Config key 'packages' must be a list.")

    changed = _staged_files()
    if not changed:
        print("No staged file changes detected.")
        return

    touched = []
    for package in packages:
        if not isinstance(package, dict):
            continue
        package_id = str(package.get("id", "")).strip()
        package_path = str(package.get("path", "")).strip()
        pyproject = str(package.get("pyproject", "")).strip()
        if not package_id or not package_path or not pyproject:
            continue
        if any(_under(path, package_path) for path in changed):
            touched.append((package_id, package_path, pyproject))

    if not touched:
        print("No package paths changed; no version stamp needed.")
        return

    for package_id, package_path, pyproject in touched:
        version = _run(
            [
                "python",
                "scripts/ci/stamp_calver.py",
                "--pyproject",
                pyproject,
                "--package-path",
                package_path,
            ]
        )
        _run(["git", "add", pyproject])
        print(f"{package_id}: {version}")


if __name__ == "__main__":
    main()
