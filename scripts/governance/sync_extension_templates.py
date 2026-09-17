"""Build/check deterministic packaged archives from Git-visible canonical template sources."""
from __future__ import annotations

import argparse
import sys
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orket.core.contracts.extension_templates import EXTENSION_TEMPLATE_SOURCES  # noqa: E402
from scripts.common.git_inventory import git_list_files  # noqa: E402


def _canonical_bytes(path: Path) -> bytes:
    payload = path.read_bytes()
    # Match Git's ordinary text newline normalization across supported checkouts;
    # UTF-8 text uses LF while opaque binary assets retain their original bytes.
    if b"\0" in payload:
        return payload
    try:
        payload.decode("utf-8")
    except UnicodeDecodeError:
        return payload
    return payload.replace(b"\r\n", b"\n")


def archive_bytes(root: Path, template_name: str, inventory: list[Path]) -> bytes:
    source = root/"docs"/"templates"/template_name
    names = sorted((p for p in inventory if p.is_relative_to(source)), key=lambda p: p.relative_to(source).as_posix())
    if not names:
        raise ValueError(f"No Git-visible template sources: {source}")
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_STORED) as archive:
        for path in names:
            if path.is_symlink():
                raise ValueError(f"Template source cannot be a symlink: {path}")
            info = ZipInfo(path.relative_to(source).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, _canonical_bytes(path))
    return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    inventory = git_list_files(ROOT)
    failures = []
    for _kind, name in EXTENSION_TEMPLATE_SOURCES:
        expected = archive_bytes(ROOT, name, inventory)
        target = ROOT/"orket"/"runtime"/"config"/"assets"/"extension_templates"/(name+".zip")
        if args.write:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(expected)
        if not target.is_file() or target.read_bytes() != expected:
            failures.append(target.relative_to(ROOT).as_posix())
    if failures:
        print("Stale or missing packaged templates: " + ", ".join(failures))
        return 1
    print("Packaged extension templates match canonical Git-visible sources.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
