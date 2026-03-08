from __future__ import annotations

import argparse
import shutil
from pathlib import Path

_TEMPLATE_DIR = Path("docs/templates/controller_workload_external")
_TEMPLATE_FILES = ("manifest.json", "extension.json", "workload_entrypoint.py")


def bootstrap_controller_external_repo(*, target_dir: Path, force: bool = False) -> Path:
    template_dir = _TEMPLATE_DIR.resolve()
    if not template_dir.exists():
        raise ValueError(f"Template directory does not exist: {template_dir}")

    destination = target_dir.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    if not force:
        existing = [name for name in _TEMPLATE_FILES if (destination / name).exists()]
        if existing:
            raise ValueError(f"Target already contains template files: {', '.join(existing)}")

    for filename in _TEMPLATE_FILES:
        shutil.copy2(template_dir / filename, destination / filename)
    return destination


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap external controller extension repository from template.")
    parser.add_argument("--target", required=True, help="Target directory for the external controller extension repo.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing template files in target.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    target = Path(str(args.target))
    bootstrap_controller_external_repo(target_dir=target, force=bool(args.force))
    print(str(target.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
