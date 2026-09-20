"""Extension checkout allocation and byte observation, called only in retained workers."""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

side_effecting = True


def allocate_checkout(install_root: Path) -> Path:
    root = install_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    # Every attempt owns a fresh directory. Failed/retired attempts remain available
    # for inspection; installation never deletes a catalog-referenced checkout.
    return Path(tempfile.mkdtemp(prefix="checkout-", dir=root))


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
