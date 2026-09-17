"""Public native wake commands preserve SQLite state, conflicts and process restarts."""
import json
import sqlite3

import pytest

from tests.helpers.governed_agent_cli import run_agent_cli
from tests.runtime.governed_agent_test_support import agent_request

pytestmark = pytest.mark.end_to_end


def cli(tmp_path, *arguments, expected=0):
    return run_agent_cli(tmp_path, "wake", *arguments, expected=expected, db_name="wake.sqlite3")


# Layer: end-to-end
def test_native_wake_admission_conflict_cancel_and_restart(tmp_path):
    request = tmp_path / "request.json"
    request.write_text(json.dumps(agent_request()), encoding="utf-8")
    arguments = (
        "enqueue", "--workload-id", "governed-agent-loop", "--occurrence-id", "native-occurrence",
        "--request", str(request), "--creation-timestamp-utc", "2041-01-01T00:00:00Z",
        "--decision-timestamp-utc", "2041-01-01T00:00:01Z",
        "--decision-timestamp-utc", "2041-01-01T00:00:02Z",
        "--next-lease-expires-at-utc", "2041-01-01T00:00:07Z",
    )
    first = cli(tmp_path, *arguments)
    repeated = cli(tmp_path, *arguments)
    wake_id = first["wake"]["wake_id"]
    assert first["status"] == "enqueued" and repeated["status"] == "idempotent"
    assert first["wake"] == repeated["wake"]
    assert cli(tmp_path, "list")["items"] == [first["wake"]]
    assert cli(tmp_path, "inspect", wake_id)["wake"] == first["wake"]
    conflict = cli(
        tmp_path, "cancel", wake_id, "--action-id", "conflict", "--actor-ref", "operator:native",
        "--timestamp-utc", "2041-01-01T00:00:02Z", "--reason", "wrong epoch",
        "--expected-cancellation-epoch", "1", "--cancellation-epoch", "2", expected=1,
    )
    assert not conflict["ok"] and conflict["error"] == "E_AGENT_WAKE_CONTROL_CONFLICT"
    assert cli(tmp_path, "inspect", wake_id)["wake"] == first["wake"]
    cancelled = cli(
        tmp_path, "cancel", wake_id, "--action-id", "cancel", "--actor-ref", "operator:native",
        "--timestamp-utc", "2041-01-01T00:00:03Z", "--reason", "operator cancelled",
        "--expected-cancellation-epoch", "0", "--cancellation-epoch", "1",
    )
    assert cancelled["wake"]["state"] == "cancelled" and not cancelled["wake"]["uncertainty"]
    assert cli(tmp_path, "inspect", wake_id)["wake"] == cancelled["wake"]
    actions = cli(tmp_path, "actions", wake_id)["items"]
    assert [item["action_id"] for item in actions] == ["conflict", "cancel"]
    with sqlite3.connect((tmp_path / "wake.sqlite3").as_uri() + "?mode=ro", uri=True) as connection:
        assert connection.execute("SELECT state, cancellation_epoch FROM governed_agent_wakes").fetchall() == [
            ("cancelled", 1),
        ]
