"""Protocol graph file effects; synchronous publication requires an owned worker."""
import json
from pathlib import Path

from orket.adapters.storage.protocol_append_only_ledger import AppendOnlyRunLedger
from orket.adapters.storage.protocol_ledger_io import owned_protocol_io
from orket.adapters.storage.verified_file import write_verified_bytes
from orket.core.contracts.run_graph import reconstruct_run_graph
from orket.core.contracts.run_graph_contract import validate_run_graph_payload

side_effecting = True


def write_run_graph_artifact(*, root: Path, session_id: str, payload: dict) -> Path:
    """Publish captured bytes by verified replacement; caller owns concurrency."""
    validate_run_graph_payload(payload)
    content = (json.dumps(payload, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
    path = Path(root) / "runs" / str(session_id).strip() / "run_graph.json"
    write_verified_bytes(path, content)
    return path


async def reconstruct_run_graph_from_events_log(*, events_log_path: Path, session_id: str | None = None) -> dict:
    """Retain file replay and graph projection in a worker through interruption."""
    path, selected = Path(events_log_path), str(session_id or "").strip()

    def reconstruct():
        events = AppendOnlyRunLedger(path).replay_events()
        return reconstruct_run_graph(events, session_id=selected or path.parent.name.strip())

    return await owned_protocol_io(reconstruct)
