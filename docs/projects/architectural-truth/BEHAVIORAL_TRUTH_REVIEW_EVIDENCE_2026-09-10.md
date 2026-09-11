# Behavioral truth review: evidence and reproductions

Date: 2026-09-10 (America/Denver)
Status: Review evidence snapshot; not a release proof or implementation plan

Companion to [the architectural review](BEHAVIORAL_TRUTH_ARCHITECTURE_REVIEW_2026-09-10.md).

## Environment and isolation

- Checkout: `C:\Source\Orket`, branch `main`, base commit `5e0dcd642dabc3a8e0c141473829e4c7228e5f8a`.
- Dirty user work existed before the review, principally local-provider integration. A provider verification document also appeared during the session. This evidence is scoped to observed worktree behavior, not a reproducible clean release build.
- Windows, Python 3.13.11, pytest 9.0.3. No dependency installation or upgrade was performed.
- `ORKET_DISABLE_SANDBOX=1`. No Docker sandbox, remote service mutation, or model-provider call was used by these probes.
- Fresh temporary directories and SQLite databases were used. Probe subprocesses performed only bounded writes beneath those directories. Successful runs removed their temporary workspaces.
- The first development run of the probe collector had an unclosed synchronous SQLite handle in the collector itself, causing Windows temporary-directory cleanup to fail after observations had printed. The collector was corrected to explicitly close that connection and rerun successfully. This was not attributed to Orket.
- The main review and this evidence document are the only repository files written by the review. Tool logs/temporary probe sources were retained under the system temporary directory during collection, not added to runtime authority or benchmark publication.

## Observed proof matrix

Here, `result=failure` means the claimed contract failed. Collecting a counterexample successfully does not make its runtime result `success`. `primary` identifies the ordinary application code path under a controlled local fixture, not a live-model or production deployment claim.

| Observation | Finding | Proof boundary | Path | Observed result |
|---|---|---|---|---|
| OLD_APPROVAL_NEW_EFFECT | SR-01 | Real application sequence, SQLite and files; model-only fixture | primary | failure |
| DUPLICATE_EFFECT | SR-02 | Concurrent real application continuations, SQLite, actual subprocess writes | primary | failure |
| COMPETING_DECISIONS | SR-03 | Concurrent real approval service and SQLite writes | primary | failure |
| EXPIRED_APPROVAL | SR-04 | Real approval/continuation and filesystem effect, explicit test clock | primary | failure |
| LEDGER_RESEAL | SR-05 | Real export, deliberate database corruption, real online-verifier service | primary | failure |
| TRUNCATED_FULL_LEDGER | SR-06 | Real export/verification over a bulk-seeded, correctly hashed database | primary | failure |
| EMPTY_VERIFIER | SR-07 | Real verifier result and real status-synthesis function; no final card persistence | primary | failure |
| CANCELLED_VERIFIER | SR-08 | Real public verifier and child process; cancellation followed by file observation | primary | failure |
| EMPTY_REPLAY | SD-02 | Real RunRecord, real SQLite repositories, real inspector | primary | failure |
| Baseline command/factory checks | Repaired July findings | Actual isolated local subprocesses | primary | success |

No row is evidence of a live llama.cpp, LM Studio, Ollama, AWS, Gitea, or Docker flow. Those paths were not attempted; there is no invented environment blocker.

## Counterexample output

Final complete probe collection exited 0. This script is an observation collector, not a green acceptance test. The following nine records are adverse observations. A remediation regression suite should assert their healthy opposites.

```text
EXPIRED_APPROVAL {"approved_at": "2026-09-10T13:00:00+00:00", "decision": "approved", "expires_at": "2026-09-10T12:00:01+00:00", "file_written": true, "run_status": "completed"}
COMPETING_DECISIONS {"events": ["proposal_pending_approval", "proposal_approved", "proposal_denied"], "returned": ["approved", "denied"], "stored": "approved"}
DUPLICATE_EFFECT {"effects": ["effect", "effect"], "returns": ["IntegrityError", "completed"], "tool_event_count": 1}
LEDGER_RESEAL {"payload": {"tampered": true}, "verifier_changed_stored_hash": true, "verify_result": "valid"}
EMPTY_VERIFIER {"checked_files": [], "commands": 0, "evidence_class": "not_evaluated", "ok": true, "synthesized": [{"args": {"status": "done"}, "tool": "update_issue_status"}]}
OLD_APPROVAL_NEW_EFFECT {"after_retry": "completed", "before_retry": "approval_required", "second_approval": "pending", "second_file_written": true}
TRUNCATED_FULL_LEDGER {"export_scope": "all", "exported_events": 5000, "stored_events": 5001, "verify_result": "valid"}
EMPTY_REPLAY {"decisions": [], "object_type": "governed_agent_replay", "run_id": "empty", "schema_version": "governed_agent_replay.v1", "status": "matched"}
CANCELLED_VERIFIER {"child_wrote_after_cancel": true, "task_cancelled": true}
```

Concurrent winning decisions and the ordering of `IntegrityError`/`completed` varied across reruns. Both competing acknowledgements and duplicate file effects were observed repeatedly. The collector intentionally uses ordinary concurrent calls without mocking storage scheduling; a future run may not hit the same race schedule.

## Verification commands and results

Executed from the checkout with the existing interpreter:

```powershell
$env:ORKET_DISABLE_SANDBOX = '1'
python -m pytest -q
python scripts/governance/check_dependency_direction.py --legacy-edge-enforcement fail --out "$env:TEMP/orket-architecture-review-20260910/dependency.json"
python scripts/governance/enforce_test_taxonomy.py --strict
python -m ruff check orket --statistics
python -m ruff check orket tests --statistics
python scripts/governance/build_architectural_truth_baseline.py --out "$env:TEMP/orket-architecture-review-20260910/baseline.json"
python scripts/governance/check_docs_project_hygiene.py
```

| Command/check | Exit/result | Evidence interpretation |
|---|---|---|
| Full pytest | 0; 4,576 passed, 73 skipped, 2 warnings; 433.18 seconds | Mixed unit/contract/integration/public-surface suite; skipped live tests do not count as live proof |
| Dependency check | 0; 834 Python files | Passes the current weaker transition policy |
| Strict taxonomy | 1; 4,272 definitions; 3,479 missing according to this checker | Prose-based checker differs from pytest marker authority |
| Ruff, `orket` | 1; 128 errors | Structural lint failure |
| Ruff, `orket tests` | 1; 154 errors | Structural failure over Quality workflow lint scope |
| Baseline collector | 0; `collection_ok=true`, `release_ready=false` | Collection success, explicit non-readiness |
| No-op inventory inside baseline | `ok=false`; 15 findings / 495 files | Includes type-only ellipsis false positives; not 15 proven runtime no-ops |
| Size inventory inside baseline | 834 files; 76 over 400 lines; 241 functions over 70; 0 parse errors | Structural change-risk indicators, not direct runtime proof |
| Docs project hygiene | 0; passed before and after review-document creation | Existing project index remains valid; roadmap unchanged |

Pytest warnings were the existing deprecated `orket.domain` import and a `GenerateRequest.max_tokens` truncation warning. No warning was treated as a pass for its underlying behavior.

The baseline ran these command cases from a temporary working directory:

| Case | Exit | Result |
|---|---:|---|
| installed_runtime_help_fresh_workspace | 0 | success |
| installed_runtime_handled_fatal | 1 | success |
| bundle_cli_help | 0 | success |
| prompts_cli_help | 0 | success |
| quickstart_help | 0 | success |
| quickstart_eof | 2 | success |
| governed_run_packaged_default | 0 | success |

The API factory observation returned distinct apps, contexts, engines and runtime states; retained both roots; found no module-default `app`; closed both contexts; and exited 0. It did not start a real HTTP server or prove all lifespan failure scenarios.

## Reproduction source

Save the following Python block to a temporary `.py` file and execute it from the Orket checkout root with the existing development environment (`python <temporary-file>`). It imports existing test helpers only for the sequential fixture-model case. It does not modify repository source or published artifacts.

The fixtures directly seed retained run/model-call state for probes that do not need model execution. That boundary is intentional: these probes test authorization, execution, persistence, and inspection after proposal creation. The old-approval case runs proposal creation and both turns through the existing composed application service with fixture model responses.

The cancellation case waits for a bounded child to finish its demonstrated post-cancel write. This is a counterexample collector for the reviewed version; after a correct cancellation fix that case will time out waiting for the forbidden effect. Convert these observations to properly classified regression tests when implementing remediation.

```python
"""Isolated integration probes; deliberately observe defects, not acceptance tests."""
import asyncio
from contextlib import closing
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path.cwd()))  # Run from the Orket checkout root.
os.environ["ORKET_DISABLE_SANDBOX"] = "1"

from orket.adapters.storage.outward_approval_store import OutwardApprovalStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.adapters.tools.registry import DEFAULT_BUILTIN_CONNECTOR_REGISTRY as REGISTRY
from orket.application.services.outward_approval_service import OutwardApprovalService
from orket.application.services.outward_ledger_service import OutwardLedgerService
from orket.application.services.outward_run_execution_service import OutwardRunExecutionService
from orket.application.services.runtime_verifier import RuntimeVerifier
from orket.application.workflows.turn_executor_runtime import synthesize_required_status_tool_call
from orket.core.domain.outward_runs import OutwardRunRecord
from orket.core.domain.outward_run_events import LedgerEvent


def emit(name, **data):
    print(name + " " + json.dumps(data, sort_keys=True), flush=True)


async def seed(root, run_id="review", tool="write_file", args=None):
    db = root / "db.sqlite3"
    runs, events, approvals = OutwardRunStore(db), OutwardRunEventStore(db), OutwardApprovalStore(db)
    await events.ensure_initialized()
    await approvals.ensure_initialized()
    now = ["2026-09-10T12:00:00+00:00"]
    args = args or {"path": "approved.txt", "content": "approved"}
    call = {"tool": tool, "args": args}
    await runs.create(OutwardRunRecord(
        run_id=run_id, status="running", namespace="review", submitted_at=now[0],
        current_turn=1, max_turns=1,
        task={"acceptance_contract": {"governed_tool_call": call}, "model_governed_tool_call": call},
        policy_overrides={"approval_required_tools": [tool]},
    ))
    service = OutwardApprovalService(approval_store=approvals, run_store=runs, event_store=events,
        connector_registry=REGISTRY, utc_now=lambda: now[0])
    proposal = await service.request_tool_approval(run_id=run_id, tool=tool, args=args,
        context_summary="review fixture", timeout_seconds=1)
    return db, runs, events, approvals, now, service, proposal


async def expiry_probe(root):
    db, runs, events, approvals, now, service, proposal = await seed(root)
    now[0] = "2026-09-10T13:00:00+00:00"
    approved = await service.approve(proposal.proposal_id, operator_ref="review")
    execution = OutwardRunExecutionService(run_store=runs, event_store=events, approval_service=service,
        connector_registry=REGISTRY, workspace_root=root, utc_now=lambda: now[0])
    result = await execution.continue_after_approval(approved.proposal_id)
    emit("EXPIRED_APPROVAL", expires_at=proposal.expires_at, approved_at=approved.decided_at,
        decision=approved.status, run_status=result.status, file_written=(root / "approved.txt").exists())


async def race_probe(root):
    db, runs, events, approvals, now, service, proposal = await seed(root)
    decisions = await asyncio.gather(
        service.approve(proposal.proposal_id, operator_ref="review-approve"),
        service.deny(proposal.proposal_id, operator_ref="review-deny", reason="denied"),
        return_exceptions=True,
    )
    stored = await approvals.get(proposal.proposal_id)
    history = await events.list_for_run("review")
    emit("COMPETING_DECISIONS", returned=[x.status if hasattr(x, "status") else repr(x) for x in decisions],
        stored=stored.status, events=[e.event_type for e in history])


async def duplicate_probe(root):
    code = "import time; from pathlib import Path; time.sleep(0.3); f=Path('effects.txt').open('a'); f.write('effect\\n'); f.close()"
    args = {"command": [sys.executable, "-c", code]}
    db, runs, events, approvals, now, service, proposal = await seed(root, tool="run_command", args=args)
    await service.approve(proposal.proposal_id, operator_ref="review")
    execution = OutwardRunExecutionService(run_store=runs, event_store=events, approval_service=service,
        connector_registry=REGISTRY, workspace_root=root, utc_now=lambda: now[0])
    results = await asyncio.gather(
        execution.continue_after_approval(proposal.proposal_id),
        execution.continue_after_approval(proposal.proposal_id), return_exceptions=True)
    history = await events.list_for_run("review")
    emit("DUPLICATE_EFFECT", effects=(root / "effects.txt").read_text().splitlines(),
        returns=[x.status if hasattr(x, "status") else type(x).__name__ for x in results],
        tool_event_count=sum(e.event_type == "tool_invoked" for e in history))


async def ledger_probe(root):
    db, runs, events, approvals, now, service, proposal = await seed(root)
    ledger = OutwardLedgerService(run_store=runs, event_store=events, utc_now=lambda: now[0])
    before = await ledger.export("review")
    event_id = before["events"][0]["event_id"]
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("UPDATE run_events SET payload_json = ? WHERE event_id = ?", ('{"tampered":true}', event_id))
        conn.commit()
    mismatched = await events.get(event_id)
    verification = await ledger.verify_run("review")
    after = await events.get(event_id)
    emit("LEDGER_RESEAL", verify_result=verification["result"], payload=after.payload,
        verifier_changed_stored_hash=after.event_hash != mismatched.event_hash)


async def verifier_probe(root):
    result = await RuntimeVerifier(root).verify()
    turn = SimpleNamespace(tool_calls=[])
    context = {"roles": ["integrity_guard"], "required_action_tools": ["update_issue_status"],
        "required_statuses": ["done", "blocked"], "runtime_verifier_ok": result.ok}
    synthesize_required_status_tool_call(turn, context)
    emit("EMPTY_VERIFIER", ok=result.ok, evidence_class=result.overall_evidence_class,
        checked_files=result.checked_files, commands=len(result.command_results),
        synthesized=[{"tool": x.tool, "args": x.args} for x in turn.tool_calls])


async def old_approval_probe(root):
    from tests.application.test_outward_run_execution_service import _execution_service, _SequenceModelClient, _Clock
    from orket.application.services.outward_run_service import OutwardRunService
    db = root / "db.sqlite3"
    clock = _Clock("2026-09-10T12:00:00+00:00")
    calls = [{"tool": "write_file", "args": {"path": name, "content": name}}
        for name in ("first.txt", "second.txt")]
    model = _SequenceModelClient(calls)
    runs, events = OutwardRunStore(db), OutwardRunEventStore(db)
    service = OutwardRunService(run_store=runs, event_store=events,
        run_id_factory=lambda: "review", utc_now=clock)
    run = await service.submit({"run_id": "review", "task": {"description": "two writes",
        "instruction": "Write two files", "acceptance_contract": {"governed_tool_sequence": calls}},
        "policy_overrides": {"approval_required_tools": ["write_file"], "max_turns": 2}})
    execution = _execution_service(db, root, clock, model_client=model)
    await execution.start_if_ready(run.run_id)
    first = (await execution.approval_service.list_pending())[0]
    await execution.approval_service.approve(first.proposal_id, operator_ref="review")
    paused = await execution.continue_after_approval(first.proposal_id)
    pending = (await execution.approval_service.list_pending())[0]
    completed = await execution.continue_after_approval(first.proposal_id)
    second = await execution.approval_service.get(pending.proposal_id)
    emit("OLD_APPROVAL_NEW_EFFECT", before_retry=paused.status, after_retry=completed.status,
        second_approval=second.status, second_file_written=(root / "second.txt").exists())


async def truncated_ledger_probe(root):
    from orket.core.domain.outward_ledger import event_hash_for, chain_hash_for
    db, runs, events, approvals, now, service, proposal = await seed(root)
    previous = "GENESIS"
    rows = []
    for i in range(5001):
        event = LedgerEvent(event_id=f"event-{i:05d}", event_type="tool_invoked", run_id="review",
            turn=1, agent_id="review", at=now[0], payload={"ordinal": i})
        digest = event_hash_for(event)
        previous = chain_hash_for(previous, digest)
        rows.append((event.event_id, event.event_type, event.run_id, event.turn, event.agent_id,
            event.at, json.dumps(event.payload), digest, previous))
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("DELETE FROM run_events")
        conn.executemany("INSERT INTO run_events VALUES (?,?,?,?,?,?,?,?,?)", rows)
        conn.commit()
    ledger = OutwardLedgerService(run_store=runs, event_store=events, utc_now=lambda: now[0])
    exported = await ledger.export("review")
    verified = await ledger.verify_run("review")
    emit("TRUNCATED_FULL_LEDGER", stored_events=len(rows), exported_events=len(exported["events"]),
        export_scope=exported["export_scope"], verify_result=verified["result"])


async def empty_replay_probe(root):
    from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
    from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
    from orket.adapters.storage.async_governed_agent_repository import AsyncGovernedAgentRepository
    from orket.application.services.governed_agent_inspection_service import GovernedAgentInspectionService
    from orket.core.contracts import RunRecord
    from orket.core.domain import RunState
    db = root / "db.sqlite3"
    execution, iterations, records = AsyncControlPlaneExecutionRepository(db), AsyncGovernedAgentRepository(db), AsyncControlPlaneRecordRepository(db)
    await execution.save_run_record(record=RunRecord(run_id="empty", workload_id="review",
        workload_version="v1", policy_snapshot_id="policy", policy_digest="sha256:" + "a" * 64,
        configuration_snapshot_id="configuration", configuration_digest="sha256:" + "b" * 64,
        creation_timestamp="2026-09-10T12:00:00Z", admission_decision_receipt_ref="admission",
        lifecycle_state=RunState.EXECUTING))
    inspector = GovernedAgentInspectionService(execution_repository=execution, iteration_repository=iterations,
        call_repository=iterations, truth_repository=records)
    emit("EMPTY_REPLAY", **await inspector.replay(run_id="empty"))


async def cancelled_verifier_probe(root):
    code = "from pathlib import Path; import time; Path('started').touch(); time.sleep(1); Path('after-cancel').write_text('effect')"
    verifier = RuntimeVerifier(root, issue_params={"runtime_verifier": {"commands": [[sys.executable, "-c", code]]}})
    task = asyncio.create_task(verifier.verify())
    async with asyncio.timeout(5):
        while not (root / "started").exists():
            await asyncio.sleep(0.01)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    async with asyncio.timeout(5):
        while not (root / "after-cancel").exists():
            await asyncio.sleep(0.05)
    await asyncio.sleep(0.1)
    emit("CANCELLED_VERIFIER", task_cancelled=task.cancelled(), child_wrote_after_cancel=(root / "after-cancel").exists())


async def main():
    with tempfile.TemporaryDirectory(prefix="orket-review-probes-") as tmp:
        for name, probe in [("expiry", expiry_probe), ("race", race_probe), ("duplicate", duplicate_probe),
            ("ledger", ledger_probe), ("verifier", verifier_probe), ("old-approval", old_approval_probe),
            ("truncated", truncated_ledger_probe), ("empty-replay", empty_replay_probe),
            ("cancelled-verifier", cancelled_verifier_probe)]:
            root = Path(tmp) / name
            root.mkdir()
            await probe(root)


asyncio.run(main())
```

## Source fingerprints

SHA-256 of exact file bytes at evidence-document creation, including CRLF where present. These pin the main reviewed counterexample paths; they do not freeze the entire dirty repository or prove that every dependency remained unchanged during the test run.

| Source | SHA-256 |
|---|---|
| [orket/application/services/outward_run_execution_service.py](../../../orket/application/services/outward_run_execution_service.py) | `ad29ab123c5558efa0b773c0b4a99fc07df4500aa99b02741905b0095480e20d` |
| [orket/application/services/outward_run_execution_plan.py](../../../orket/application/services/outward_run_execution_plan.py) | `0efa64a94c1b3af20ff1246c606c1a02aad60efbaca52f9cec85cc9623d86998` |
| [orket/application/services/outward_approval_service.py](../../../orket/application/services/outward_approval_service.py) | `89ce9798f4ce3669b513e43fb71bae2ec9e95c41cd01fb4201a0655e00b8416d` |
| [orket/adapters/storage/outward_approval_store.py](../../../orket/adapters/storage/outward_approval_store.py) | `e8ca8d49ac84f8ccc7ad9ee4ea50e7b953d867524fabffdbaccf409910ce692d` |
| [orket/adapters/storage/outward_run_store.py](../../../orket/adapters/storage/outward_run_store.py) | `20b62d6664c4921a1d7314b20a5beae05a6a21503437a4088db5ad21f3729b45` |
| [orket/adapters/storage/outward_run_event_store.py](../../../orket/adapters/storage/outward_run_event_store.py) | `01d7f82dff83ed43af7906ad26308200e97098ae34532aa3144cfb6704b9fa16` |
| [orket/application/services/outward_ledger_service.py](../../../orket/application/services/outward_ledger_service.py) | `2f0620a33b56ff0e09b942943b7204596c2a267f9f5903759facc476767b5727` |
| [orket/core/domain/outward_ledger.py](../../../orket/core/domain/outward_ledger.py) | `c8fb7861751c64473ec22d4a2d7ec65deb197d9fd42aff715d992487ad0718ff` |
| [orket/application/services/outward_connector_service.py](../../../orket/application/services/outward_connector_service.py) | `2bbeb212116920e7175dd136ac938b524b4ef26fb6dd48b550bc39447cfdfd1c` |
| [orket/adapters/tools/builtin_connectors.py](../../../orket/adapters/tools/builtin_connectors.py) | `bcbf708b9fe62a86468eac496b5a2e66b224ddd72ddeca5826ddd931b91614f9` |
| [orket/application/services/runtime_verifier.py](../../../orket/application/services/runtime_verifier.py) | `6b1d1436735e8454086e13cbc3a2f71f6ed5d9594ad515811c871ddd94ad6509` |
| [orket/application/workflows/turn_executor_runtime.py](../../../orket/application/workflows/turn_executor_runtime.py) | `49f3b01fc74bc818ea4093c5bbfd478b210b9eec21c89c5cc9ee7b5cadb0c23b` |
| [orket/application/services/governed_agent_inspection_service.py](../../../orket/application/services/governed_agent_inspection_service.py) | `dd9dd71c639db3693bd0810b1137b83df38fdb20f7136de06746e741c7b1a150` |
| [orket/runtime/execution/epic_run_finalize.py](../../../orket/runtime/execution/epic_run_finalize.py) | `1c667efbeea4df1d4dfda18a17b9cb711d546c8f149f8d26562e2c2cdf6ca155` |
| [orket/interfaces/cli.py](../../../orket/interfaces/cli.py) | `19ab749dd209d0df25827bcabf4ab93ac99c2ba33b3de7e800b2e5c70ebe5b34` |
| [tests/application/test_outward_run_execution_service.py](../../../tests/application/test_outward_run_execution_service.py) | `a88e0220665028d8d3b77b6307d2bbb2465a641cb965c5a17a1b74239756171b` |
