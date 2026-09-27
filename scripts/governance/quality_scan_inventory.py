"""Git-visible source selection shared by the quality checkers."""

from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.common.git_inventory import GitInventoryError, git_list_files


def git_visible_python_files(roots: list[Path]) -> list[Path]:
    if not roots:
        raise GitInventoryError("scan_roots_empty")
    roots = [root.resolve(strict=True) for root in roots]
    anchor = roots[0] if roots[0].is_dir() else roots[0].parent
    discovery = subprocess.run(
        ["git", "-C", str(anchor), "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=False,
    )
    if discovery.returncode:
        raise GitInventoryError(discovery.stderr.strip())
    repository = Path(discovery.stdout.strip()).resolve(strict=True)
    if any(not root.is_relative_to(repository) for root in roots):
        raise GitInventoryError("scan_roots_span_repositories")
    return [
        path for path in git_list_files(repository)
        if path.suffix == ".py" and any(path == root or path.is_relative_to(root) for root in roots)
    ]
