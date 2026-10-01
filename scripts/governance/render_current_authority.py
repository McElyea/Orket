"""Generate the bounded authority snapshot after canonical source validation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.common.git_inventory import GitInventoryError
from scripts.governance.current_authority import VIEW, output_path, validate
from scripts.governance.current_authority_view import render


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload, sources, _ = validate(Path(args.repo_root))
        expected = render(payload)
        if args.check:
            sources.read(VIEW)
            sources.recheck()
            if sources.observed[VIEW] != expected:
                raise ValueError("generated authority differs")
        else:
            destination = output_path(sources, VIEW, view=True)
            destination.write_bytes(expected)
            if destination.read_bytes() != expected:
                raise ValueError("generated authority readback differs")
            sources.recheck()
        return 0
    except (ValueError, OSError, UnicodeError, SyntaxError, GitInventoryError) as exc:
        print(f"authority rendering refused: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
