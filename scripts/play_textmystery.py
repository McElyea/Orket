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
    parser = argparse.ArgumentParser(description="Launch TextMystery interactive play mode.")
    parser.add_argument("--textmystery-root", default=None, help="Path to TextMystery project root.")
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--scene", default="SCENE_001")
    parser.add_argument("--difficulty", choices=["normal", "hard"], default="normal")
    args = parser.parse_args()

    root = _resolve_textmystery_root(args.textmystery_root)
    src_path = root / "src"
    if not src_path.exists():
        print(f"[FAIL] TextMystery src not found at: {src_path}")
        print("Set --textmystery-root or TEXTMYSTERY_ROOT.")
        return 1

    env = dict(os.environ)
    orket_root = str(Path(__file__).resolve().parents[1])
    existing = str(env.get("PYTHONPATH", "")).strip()
    paths = [str(src_path), orket_root]
    if existing:
        paths.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(paths)

    cmd = [
        sys.executable,
        "-m",
        "textmystery.cli.main",
        "--play",
        "--seed",
        str(args.seed),
        "--scene",
        args.scene,
        "--difficulty",
        args.difficulty,
    ]
    return subprocess.run(cmd, env=env).returncode


if __name__ == "__main__":
    raise SystemExit(main())
