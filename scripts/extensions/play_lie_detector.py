from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _resolve_textmystery_root(args_root: str | None) -> Path:
    if args_root:
        return Path(args_root).resolve()
    env_root = str(os.getenv("TEXTMYSTERY_ROOT", "")).strip()
    if env_root:
        return Path(env_root).resolve()
    return Path(r"C:\Source\Orket-Extensions\TextMystery")


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch The Lie Detector game mode.")
    parser.add_argument("--textmystery-root", default=None, help="Path to TextMystery project root.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--floors", type=int, default=None)
    parser.add_argument("--plain", action="store_true", help="No ANSI rendering.")
    parser.add_argument("--llm-model", default="llama3.1:8b")
    parser.add_argument("--no-llm", action="store_true", help="Template-only mode.")
    args = parser.parse_args()

    root = _resolve_textmystery_root(args.textmystery_root)
    src_path = root / "src"
    if not src_path.exists():
        print(f"[FAIL] TextMystery src not found at: {src_path}")
        print("Set --textmystery-root or TEXTMYSTERY_ROOT.")
        return 1

    env = dict(os.environ)
    orket_root = str(Path(__file__).resolve().parents[2])
    existing = str(env.get("PYTHONPATH", "")).strip()
    paths = [str(src_path), orket_root]
    if existing:
        paths.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(paths)

    cmd = [
        sys.executable,
        "-m",
        "textmystery.cli.lie_detector_cli",
        "--seed",
        str(args.seed),
    ]
    if args.floors is not None:
        cmd.extend(["--floors", str(args.floors)])
    if args.plain:
        cmd.append("--plain")
    if args.no_llm:
        cmd.append("--no-llm")
    else:
        cmd.extend(["--llm-model", args.llm_model])

    return subprocess.run(cmd, env=env).returncode


if __name__ == "__main__":
    raise SystemExit(main())
