"""Read-only probe copied outside the checkout and run by the candidate interpreter."""
from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import platform
import sys
import zipfile
from pathlib import Path


def inspect_distribution(wheel: Path, name: str, namespace: str, prefix: Path, checkout: Path) -> dict:
    distribution = importlib.metadata.distribution(name)
    module = importlib.import_module(namespace)
    origin = Path(module.__file__).resolve()
    if not origin.is_relative_to(prefix) or origin.is_relative_to(checkout):
        raise ValueError(f"Import escaped isolated candidate installation: {namespace}")
    owners = importlib.metadata.packages_distributions().get(namespace, [])
    if [owner.replace("_", "-").lower() for owner in owners] != [name]:
        raise ValueError(f"Unexpected namespace owners for {namespace}: {owners}")
    direct = json.loads(distribution.read_text("direct_url.json") or "{}")
    expected_hash = hashlib.sha256(wheel.read_bytes()).hexdigest()
    if direct.get("archive_info", {}).get("hashes", {}).get("sha256") != expected_hash:
        raise ValueError(f"Installed distribution does not identify the candidate wheel: {name}")
    count = 0
    with zipfile.ZipFile(wheel) as archive:
        for item in archive.namelist():
            if not item.startswith(namespace + "/") or item.endswith("/"):
                continue
            installed = Path(distribution.locate_file(item)).resolve()
            if not installed.is_relative_to(prefix) or installed.read_bytes() != archive.read(item):
                raise ValueError(f"Installed bytes differ from candidate: {item}")
            count += 1
    return {"name": name, "version": distribution.version, "origin": str(origin),
            "wheel_sha256": expected_hash, "installed_files_checked": count, "namespace_owners": owners}


def main() -> None:
    checkout, prefix, core, sdk = map(lambda value: Path(value).resolve(), sys.argv[1:])
    if Path(sys.prefix).resolve() != prefix or prefix.is_relative_to(checkout):
        raise ValueError("Candidate interpreter is not in the isolated external environment")
    if any(Path(value).resolve().is_relative_to(checkout) for value in sys.path):
        raise ValueError("Source checkout leaked into candidate import search path")
    records = [inspect_distribution(core, "orket", "orket", prefix, checkout),
               inspect_distribution(sdk, "orket-extension-sdk", "orket_extension_sdk", prefix, checkout)]
    # Emits evidence to the parent-owned log; it does not write a separate JSON result.
    print(json.dumps({"distributions": records, "system": platform.system(), "machine": platform.machine(),
                      "python": platform.python_version(), "prefix": str(prefix), "executable": sys.executable}))


if __name__ == "__main__":
    main()
