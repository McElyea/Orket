# Mesh Orchestration Prototype

## Architecture
- `mesh_orchestration/card.py` defines `Card` with lease-aware fields and strict states: `OPEN`, `CLAIMED`, `DONE`, `FAILED`.
- `mesh_orchestration/coordinator.py` runs a FastAPI coordinator over an in-memory store and enforces claim, renew, complete (idempotent), and fail rules.
- `mesh_orchestration/worker.py` implements polling workers that compete on claims, renew leases during work, and finalize with complete/fail.

## Run Local
1. Install dependencies: `pip install fastapi uvicorn httpx pydantic`.
2. Run coordinator only: `python -m uvicorn mesh_orchestration.coordinator:app --host 127.0.0.1 --port 8000`.
3. Run the 3-worker crash/takeover demo: `python -m mesh_orchestration.run_demo`.

