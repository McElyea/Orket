from __future__ import annotations

import multiprocessing as mp
import os
import time

import httpx
import uvicorn

from mesh_orchestration.worker import run_worker


def run_server(port: int) -> None:
    uvicorn.run(
        "mesh_orchestration.coordinator:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )


def wait_for_server(base_url: str, timeout_seconds: float = 10.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = httpx.get(f"{base_url}/cards?state=open", timeout=1.0)
            if response.status_code == 200:
                return
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.2)
    raise RuntimeError("server did not become ready")


def main() -> None:
    mp.set_start_method("spawn", force=True)
    port = int(os.environ.get("MESH_COORDINATOR_PORT", "8011"))
    base_url = f"http://127.0.0.1:{port}"

    server_proc = mp.Process(target=run_server, args=(port,), name="coordinator", daemon=True)
    server_proc.start()
    wait_for_server(base_url)

    workers = [
        mp.Process(
            target=run_worker,
            kwargs={
                "node_id": "worker-1",
                "base_url": base_url,
                "crash_after_claim": True,
                "max_runtime_seconds": 12,
            },
            name="worker-1",
        ),
        mp.Process(
            target=run_worker,
            kwargs={"node_id": "worker-2", "base_url": base_url, "max_runtime_seconds": 20},
            name="worker-2",
        ),
        mp.Process(
            target=run_worker,
            kwargs={"node_id": "worker-3", "base_url": base_url, "max_runtime_seconds": 20},
            name="worker-3",
        ),
    ]

    workers[0].start()
    time.sleep(0.75)
    workers[1].start()
    workers[2].start()

    for process in workers:
        process.join(timeout=30)

    for process in workers:
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)

    final_cards = httpx.get(f"{base_url}/cards?state=open", timeout=2.0).json()
    print(f"[demo] open cards after run: {final_cards}")

    server_proc.terminate()
    server_proc.join(timeout=5)


if __name__ == "__main__":
    main()
