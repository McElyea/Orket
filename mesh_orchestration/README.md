# Mesh Orchestration Prototype

Prototype coordinator/worker flow for lease-based card execution.

## Components
1. `mesh_orchestration/card.py`: card model and lease fields.
2. `mesh_orchestration/coordinator.py`: FastAPI coordinator and claim/renew/complete/fail endpoints.
3. `mesh_orchestration/worker.py`: polling workers with lease renewal.
4. `mesh_orchestration/run_demo.py`: multi-worker demo runner.

## Run
1. Install minimum dependencies:
```bash
pip install fastapi uvicorn httpx pydantic
```
2. Start coordinator:
```bash
python -m uvicorn mesh_orchestration.coordinator:app --host 127.0.0.1 --port 8000
```
3. Run demo workers:
```bash
python -m mesh_orchestration.run_demo
```
