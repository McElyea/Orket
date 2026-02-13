from __future__ import annotations

import argparse
import asyncio
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _run(cmd: list[str]) -> None:
    print(f"[release-smoke] RUN: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def _wait_for_health(url: str, timeout_sec: int) -> None:
    start = time.time()
    last_error = ""
    while time.time() - start < timeout_sec:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    print("[release-smoke] Health probe succeeded")
                    return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
        time.sleep(1)
    raise RuntimeError(f"Health probe failed after {timeout_sec}s: {last_error}")


def _docker_smoke(image_tag: str, port: int, timeout_sec: int) -> None:
    if shutil.which("docker") is None:
        raise RuntimeError("Docker is not installed or not found in PATH.")

    container_name = "orket-release-smoke"
    _run(["docker", "build", "-t", image_tag, "."])
    _run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "-p",
            f"{port}:8082",
            image_tag,
        ]
    )

    try:
        _wait_for_health(f"http://127.0.0.1:{port}/health", timeout_sec)
    finally:
        subprocess.run(["docker", "rm", "-f", container_name], check=False)


async def _bootstrap_databases(runtime_db: str, webhook_db: str) -> None:
    from orket.infrastructure.async_card_repository import AsyncCardRepository
    from orket.services.webhook_db import WebhookDatabase

    runtime_repo = AsyncCardRepository(runtime_db)
    await runtime_repo.get_by_build("_release_smoke_bootstrap_")

    webhook_repo = WebhookDatabase(Path(webhook_db))
    await webhook_repo.get_active_prs()


def main() -> None:
    parser = argparse.ArgumentParser(description="One-command local release smoke")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--skip-security-canary", action="store_true")
    parser.add_argument("--skip-migrations", action="store_true")
    parser.add_argument("--skip-docker", action="store_true")
    parser.add_argument("--runtime-db", default=".smoke/runtime.db")
    parser.add_argument("--webhook-db", default=".smoke/webhook.db")
    parser.add_argument("--docker-image-tag", default="orket:release-smoke")
    parser.add_argument("--docker-port", type=int, default=8082)
    parser.add_argument("--docker-health-timeout-sec", type=int, default=60)
    args = parser.parse_args()

    Path(".smoke").mkdir(parents=True, exist_ok=True)

    if not args.skip_tests:
        _run(["python", "-m", "pytest", "tests/", "-q"])

    if not args.skip_security_canary:
        _run(["python", "scripts/security_canary.py"])

    if not args.skip_migrations:
        print("[release-smoke] Bootstrapping database schemas")
        asyncio.run(_bootstrap_databases(args.runtime_db, args.webhook_db))
        _run(
            [
                "python",
                "scripts/run_migrations.py",
                "--runtime-db",
                args.runtime_db,
                "--webhook-db",
                args.webhook_db,
            ]
        )

    if not args.skip_docker:
        _docker_smoke(args.docker_image_tag, args.docker_port, args.docker_health_timeout_sec)

    print("[release-smoke] SUCCESS")


if __name__ == "__main__":
    main()
