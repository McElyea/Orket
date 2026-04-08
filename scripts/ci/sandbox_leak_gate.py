from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fail when Orket-managed sandbox resources leak after acceptance.")
    parser.add_argument(
        "--allowlist-env",
        default="ORKET_SANDBOX_LEAK_ALLOWLIST",
        help="Environment variable containing comma-separated resource names to ignore.",
    )
    return parser


def _allowlist(env_name: str) -> set[str]:
    return {item.strip() for item in os.getenv(env_name, "").split(",") if item.strip()}


def _command_failure_message(cmd: list[str] | tuple[str, ...], completed: subprocess.CompletedProcess[str]) -> str:
    detail = (completed.stderr or completed.stdout or "no output").strip()
    return f"{' '.join(cmd)} failed with exit {completed.returncode}: {detail}"


def _lines(*cmd: str) -> list[str]:
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(_command_failure_message(cmd, completed))
    return sorted(line.strip() for line in completed.stdout.splitlines() if line.strip())


def _compose_projects() -> list[dict[str, object]]:
    cmd = ["docker-compose", "ls", "--format", "json"]
    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(_command_failure_message(cmd, completed))
    try:
        payload = json.loads(completed.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError("docker-compose ls returned invalid JSON") from exc
    return payload if isinstance(payload, list) else []


def evaluate_leaks(allow: set[str]) -> dict[str, list[str]]:
    projects = _compose_projects()
    return {
        "compose_projects": sorted(
            name
            for name in (str(item.get("Name") or "") for item in projects if isinstance(item, dict))
            if name.startswith("orket-sandbox-") and name not in allow
        ),
        "containers": [
            name
            for name in _lines("docker", "ps", "-a", "--filter", "label=orket.managed=true", "--format", "{{.Names}}")
            if name not in allow
        ],
        "networks": [
            name
            for name in _lines("docker", "network", "ls", "--filter", "label=orket.managed=true", "--format", "{{.Name}}")
            if name not in allow
        ],
        "volumes": [
            name
            for name in _lines("docker", "volume", "ls", "--filter", "label=orket.managed=true", "--format", "{{.Name}}")
            if name not in allow
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        leaks = evaluate_leaks(_allowlist(str(args.allowlist_env)))
    except RuntimeError as exc:
        print(f"Sandbox leak gate failed: {exc}")
        return 1
    if any(leaks.values()):
        print("Sandbox leak gate failed")
        for key in ("compose_projects", "containers", "networks", "volumes"):
            print(f"{key}={leaks[key]}")
        return 1
    print("Sandbox leak gate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
