#!/usr/bin/env python3
"""Detect changed monorepo packages for CI path-scoped jobs."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any


def _run_git(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _safe_rel_posix(path_text: str) -> str:
    return Path(path_text).as_posix().strip("/")


def _load_config(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Config must be a JSON object.")
    return data


def _path_in_prefixes(path: str, prefixes: list[str]) -> bool:
    for prefix in prefixes:
        norm = _safe_rel_posix(prefix)
        if not norm:
            continue
        if path == norm or path.startswith(f"{norm}/"):
            return True
    return False


def _detect_changed_files(base_ref: str) -> list[str]:
    try:
        _run_git(["rev-parse", "--verify", base_ref])
        diff_text = _run_git(["diff", "--name-only", "--diff-filter=ACMR", f"{base_ref}...HEAD"])
        if diff_text:
            return [line.strip() for line in diff_text.splitlines() if line.strip()]
    except RuntimeError:
        pass

    # Fallback for shallow clones/new branches.
    try:
        diff_text = _run_git(["diff", "--name-only", "--diff-filter=ACMR", "HEAD~1...HEAD"])
        if diff_text:
            return [line.strip() for line in diff_text.splitlines() if line.strip()]
    except RuntimeError:
        pass

    return []


def _emit_output(key: str, value: str) -> None:
    output_file = os.getenv("GITHUB_OUTPUT", "").strip()
    if output_file:
        with open(output_file, "a", encoding="utf-8") as handle:
            handle.write(f"{key}={value}\n")
    print(f"{key}={value}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect changed packages for monorepo CI.")
    parser.add_argument("--config", default=".ci/packages.json", help="Package config JSON path.")
    parser.add_argument("--base-ref", default="origin/main", help="Git ref used as diff base.")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        raise SystemExit(f"Config file not found: {config_path}")

    config = _load_config(config_path)
    packages = config.get("packages", [])
    if not isinstance(packages, list):
        raise SystemExit("Config key 'packages' must be a list.")

    global_paths = config.get("global_trigger_paths", [])
    if not isinstance(global_paths, list):
        raise SystemExit("Config key 'global_trigger_paths' must be a list.")

    changed_files = [_safe_rel_posix(p) for p in _detect_changed_files(args.base_ref)]
    changed_set = set(changed_files)

    package_matrix: list[dict[str, Any]] = []
    for item in packages:
        if not isinstance(item, dict):
            raise SystemExit("Each package config entry must be an object.")
        package_id = str(item.get("id", "")).strip()
        package_path = _safe_rel_posix(str(item.get("path", "")).strip())
        if not package_id or not package_path:
            raise SystemExit("Each package requires non-empty 'id' and 'path'.")
        package_matrix.append(item)

    run_all = _path_in_prefixes_any(changed_set, [_safe_rel_posix(p) for p in global_paths]) if changed_set else False
    if run_all:
        selected = package_matrix
    else:
        selected = []
        for item in package_matrix:
            package_path = _safe_rel_posix(str(item["path"]))
            if _path_in_prefixes_any(changed_set, [package_path]):
                selected.append(item)

    selected_ids = [str(item["id"]) for item in selected]
    _emit_output("changed_files", json.dumps(sorted(changed_set)))
    _emit_output("matrix", json.dumps(selected))
    _emit_output("changed_ids", ",".join(selected_ids))
    _emit_output("any_changed", "true" if selected else "false")


def _path_in_prefixes_any(changed_set: set[str], prefixes: list[str]) -> bool:
    for path in changed_set:
        if _path_in_prefixes(path, prefixes):
            return True
    return False


if __name__ == "__main__":
    main()
