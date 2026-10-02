"""Output projection contracts; rendered claims are not evidence of native execution."""
import json
from copy import deepcopy

import pytest

from orket.interfaces.bundle_cli_output import emit_result, render_human

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("control_plane,expected", [
    (None, []), ({}, []), ({"run_state": "waiting", "run_id": "run-1"},
        ["control-plane: run=waiting", "control-plane refs: run_id=run-1"]),
    ({"attempt_state": "interrupted", "step_kind": "review", "attempt_id": "attempt-1", "step_id": "step-1"},
        ["control-plane: attempt=interrupted step=review", "control-plane refs: attempt_id=attempt-1 step_id=step-1"]),
])
def test_review_output_preserves_only_supplied_authority_fields(control_plane, expected):
    payload = dict(run_id="run-1", deterministic_decision="blocked", artifact_dir="artifacts/run-1",
        control_plane=control_plane, verbose=True, snapshot_digest="sha256:snapshot", policy_digest="sha256:policy")
    before = deepcopy(payload)
    assert render_human(payload).splitlines() == [
        "run_id: run-1", "deterministic decision: blocked", "artifact path: artifacts/run-1", *expected,
        "snapshot_digest: sha256:snapshot", "policy_digest: sha256:policy"]
    assert payload == before


def test_transaction_failure_keeps_advisories_warnings_parity_and_verifier_tail():
    payload = dict(ok=False, code="E_VERIFY_FAILED", message="reverted", plan="Planned operation",
        advisories=[None, {"score": 0.8, "lesson_id": "lesson-1", "summary": "check input"}],
        preflight_warnings=["scope needs attention", "verifier unavailable"],
        parity={"status": "reverted", "changed_file_count": 0, "artifact_path": "parity.json"},
        verify_output_tail="native verifier tail")
    before = deepcopy(payload)
    assert render_human(payload) == (
        "Planned operation\nFAILURE LESSON ADVISORIES:\n  - [0.8] lesson-1: check input\n"
        "PREFLIGHT WARNINGS:\n  - scope needs attention\n  - verifier unavailable\n"
        "FAIL [E_VERIFY_FAILED]: reverted\nPARITY: status=reverted, changed_files=0\n"
        "PARITY ARTIFACT: parity.json\n\nnative verifier tail")
    assert payload == before


@pytest.mark.parametrize("payload,expected", [
    ({"kind": "governed_run_execution", "console_output": "retained output"}, "retained output"),
    ({"kind": "governed_run_execution"}, ""),
    ({"kind": "governed_run_error", "code": "E_REFUSED", "message": "blocked"}, "FAIL [E_REFUSED]: blocked"),
    ({"ok": True, "extension_id": "fixture", "workload_count": 2}, "OK: fixture (workloads=2, warnings=0)"),
    ({"ok": True, "extension_id": "fixture", "workload_count": 2, "warning_count": 1},
        "OK: fixture (workloads=2, warnings=1)"),
    ({"operation": "ext.init", "ok": True, "target": "destination", "copied_file_count": 3},
        "OK: scaffolded external extension at destination (files=3)"),
])
def test_result_kinds_keep_distinct_user_messages(payload, expected):
    assert render_human(payload) == expected


@pytest.mark.parametrize("kind", [{"extension_id": "fixture", "workload_count": 0}, {"operation": "ext.init"}])
@pytest.mark.parametrize("errors", [[], [{"code": "E_INVALID", "location": "manifest", "message": "refused"}]])
def test_extension_validation_and_scaffold_refusals_keep_error_details(kind, errors):
    payload = {**kind, "ok": False, "error_count": len(errors), "errors": errors}
    expected = [f"FAIL ({len(errors)} error(s))"]
    if errors:
        expected.append("[E_INVALID] manifest: refused")
    assert render_human(payload).splitlines() == expected


@pytest.mark.parametrize("emit_json", [False, True])
@pytest.mark.parametrize("ok,exit_code", [(True, 3), (False, 0), (False, None), (True, None)])
def test_emitter_preserves_explicit_exit_status_and_unicode_payload(capsys, emit_json, ok, exit_code):
    payload = {"ok": ok, "code": "E_FIXTURE", "message": "résultat", "exit_code": exit_code}
    before = deepcopy(payload)
    observed = emit_result(payload, emit_json=emit_json)
    captured = capsys.readouterr()
    assert observed == (exit_code if exit_code is not None else (0 if ok else 1))
    assert captured.err == "" and "résultat" in captured.out
    if emit_json:
        assert json.loads(captured.out) == payload
    else:
        assert captured.out == ("OK" if ok else "FAIL [E_FIXTURE]") + ": résultat\n"
    assert payload == before
