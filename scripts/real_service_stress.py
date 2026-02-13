from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _wait_for_health(url: str, timeout_sec: int) -> None:
    start = time.time()
    last_error = ""
    while time.time() - start < timeout_sec:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
        time.sleep(1)
    raise RuntimeError(f"Health probe failed for {url} after {timeout_sec}s: {last_error}")


def _start_process(cmd: list[str], env: dict[str, str], log_path: Path) -> subprocess.Popen:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("w", encoding="utf-8")
    return subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _profile_args(profile: str) -> dict[str, int]:
    if profile == "aggressive":
        return {
            "webhook_total": 4000,
            "webhook_concurrency": 200,
            "api_total": 8000,
            "api_concurrency": 300,
            "epic_total": 500,
            "epic_concurrency": 150,
            "ws_clients": 800,
        }
    if profile == "heavy":
        return {
            "webhook_total": 1500,
            "webhook_concurrency": 100,
            "api_total": 3000,
            "api_concurrency": 150,
            "epic_total": 200,
            "epic_concurrency": 80,
            "ws_clients": 300,
        }
    return {
        "webhook_total": 300,
        "webhook_concurrency": 40,
        "api_total": 600,
        "api_concurrency": 60,
        "epic_total": 40,
        "epic_concurrency": 20,
        "ws_clients": 100,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run real-service stress load against Orket API + webhook.")
    parser.add_argument("--profile", choices=["baseline", "heavy", "aggressive"], default="heavy")
    parser.add_argument("--api-port", type=int, default=8082)
    parser.add_argument("--webhook-port", type=int, default=8080)
    parser.add_argument("--health-timeout-sec", type=int, default=90)
    parser.add_argument("--out", default="", help="Optional output json path for load report.")
    parser.add_argument("--api-key", default="stress-api-key")
    parser.add_argument("--webhook-test-token", default="stress-webhook-token")
    args = parser.parse_args()

    load = _profile_args(args.profile)
    out_path = args.out or f"benchmarks/results/{int(time.time())}_real_service_{args.profile}.json"

    env = dict(os.environ)
    env["ORKET_API_KEY"] = args.api_key
    env["GITEA_ADMIN_PASSWORD"] = env.get("GITEA_ADMIN_PASSWORD", "test-pass")
    env["GITEA_WEBHOOK_SECRET"] = env.get("GITEA_WEBHOOK_SECRET", "test-secret")
    env["ORKET_ENABLE_WEBHOOK_TEST_ENDPOINT"] = "true"
    env["ORKET_WEBHOOK_TEST_TOKEN"] = args.webhook_test_token

    api_proc = None
    webhook_proc = None
    try:
        api_proc = _start_process(
            [sys.executable, "server.py"],
            env=env,
            log_path=PROJECT_ROOT / ".smoke" / "api_stress.log",
        )
        webhook_proc = _start_process(
            [sys.executable, "-m", "orket.webhook_server"],
            env=env,
            log_path=PROJECT_ROOT / ".smoke" / "webhook_stress.log",
        )

        _wait_for_health(f"http://127.0.0.1:{args.api_port}/health", args.health_timeout_sec)
        _wait_for_health(f"http://127.0.0.1:{args.webhook_port}/health", args.health_timeout_sec)

        cmd = [
            sys.executable,
            "benchmarks/phase5_load_test.py",
            "--webhook-base-url",
            f"http://127.0.0.1:{args.webhook_port}",
            "--api-base-url",
            f"http://127.0.0.1:{args.api_port}",
            "--ws-url",
            f"ws://127.0.0.1:{args.api_port}/ws/events",
            "--webhook-total",
            str(load["webhook_total"]),
            "--webhook-concurrency",
            str(load["webhook_concurrency"]),
            "--api-total",
            str(load["api_total"]),
            "--api-concurrency",
            str(load["api_concurrency"]),
            "--epic-total",
            str(load["epic_total"]),
            "--epic-concurrency",
            str(load["epic_concurrency"]),
            "--ws-clients",
            str(load["ws_clients"]),
            "--out",
            out_path,
        ]
        print(f"[real-service-stress] Running profile={args.profile}")
        subprocess.run(cmd, check=True, cwd=str(PROJECT_ROOT), env=env)
        print(f"[real-service-stress] SUCCESS report={out_path}")
    finally:
        for proc in [api_proc, webhook_proc]:
            if proc is None:
                continue
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
