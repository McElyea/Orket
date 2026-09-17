"""Pure validation and durable-observation requirements for dual ledger intents."""
from typing import Any

from orket.core.contracts.protocol_error_codes import E_DUAL_WRITE_PREFIX, format_protocol_error
from orket.core.contracts.result_error_invariants import validate_result_error_invariant


class DualWriteLedgerError(RuntimeError):
    """Pending state cannot safely be acknowledged, replaced or replayed."""

    def __init__(self, detail):
        super().__init__(format_protocol_error(E_DUAL_WRITE_PREFIX, detail))


def validate_intent(intent: Any) -> None:
    if not isinstance(intent, dict):
        raise DualWriteLedgerError("INTENT_SCHEMA:row")
    operation, session = intent.get("operation"), intent.get("session_id")
    kwargs = intent.get("kwargs")
    if (operation not in ("start_run", "finalize_run") or not isinstance(session, str) or not session.strip()
            or session != session.strip()
            or session in (".", "..") or "/" in session or "\\" in session
            or intent.get("intent_id") != f"{operation}:{session}" or not isinstance(kwargs, dict)
            or kwargs.get("session_id") != session):
        raise DualWriteLedgerError("INTENT_SCHEMA:identity")
    required = ("run_type", "run_name", "department", "build_id") if operation == "start_run" else ("status",)
    allowed = {"session_id", "summary", "artifacts", *required}
    if operation == "finalize_run":
        allowed.update(("failure_class", "failure_reason", "finalized_at"))
    if set(kwargs) - allowed or any(not isinstance(kwargs.get(name), str) for name in required):
        raise DualWriteLedgerError("INTENT_SCHEMA:arguments")
    if any(kwargs.get(name) is not None and not isinstance(kwargs[name], dict) for name in ("summary", "artifacts")):
        raise DualWriteLedgerError("INTENT_SCHEMA:payload")
    if any(type(intent.get(name)) is not bool for name in ("sqlite_ack", "protocol_ack")):
        raise DualWriteLedgerError("INTENT_SCHEMA:acknowledgement")
    if any(kwargs.get(name) is not None and not isinstance(kwargs[name], str)
           for name in ("failure_class", "failure_reason", "finalized_at")):
        raise DualWriteLedgerError("INTENT_SCHEMA:finalization")
    if operation == "finalize_run":
        status = validate_result_error_invariant(status=kwargs["status"], failure_class=kwargs.get("failure_class"),
                                                failure_reason=kwargs.get("failure_reason"))
        if status != kwargs["status"]:
            raise DualWriteLedgerError("INTENT_SCHEMA:status")


def intent_matches_row(intent: dict, row: dict | None) -> bool:
    """Require the requested content; journal acknowledgement flags are not proof."""
    if row is None:
        return False
    kwargs = intent["kwargs"]
    if row.get("session_id") != intent["session_id"]:
        return False
    if intent["operation"] == "start_run":
        fields = ("run_type", "run_name", "department", "build_id")
    else:
        fields = ("status", "failure_class", "failure_reason")
    if any(row.get(name) != kwargs.get(name) for name in fields):
        return False
    if kwargs.get("finalized_at") is not None and row.get("ended_at") != kwargs["finalized_at"]:
        return False
    for supplied, stored in (("summary", "summary_json"), ("artifacts", "artifact_json")):
        expected, actual = kwargs.get(supplied), row.get(stored)
        if not isinstance(actual, dict):
            return False
        if expected is not None and any(key not in actual or actual[key] != value for key, value in expected.items()):
            return False
    return True


def require_replayable(intent: dict, row: dict | None) -> None:
    if intent_matches_row(intent, row):
        return
    if intent["operation"] == "start_run" and row is None:
        return
    if intent["operation"] == "finalize_run" and row is not None and row.get("status") == "running":
        return
    raise DualWriteLedgerError(f"CONTENT_CONFLICT:{intent['intent_id']}")
