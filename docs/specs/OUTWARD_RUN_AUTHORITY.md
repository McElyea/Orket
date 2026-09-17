# Outward shared run authority

Status: Active contract; shared outward cutover accepted within BT-5
Last updated: 2026-09-14
Owner: Orket Core

## Admission and ownership

`outward_control_plane_service.py` resolves `outward-governed-tools` from the
canonical control-plane workload catalog. The existing outward unit of work owns
one SQLite transaction for the protocol run, admission event, shared run/attempt,
and immutable policy/configuration snapshots. There is no second database or
workload-ID allocator. `outward:<run_id>:generation:<execution_generation>` remains
the attempt identity already used by effect authorization.

The configuration snapshot binds the submitted task, namespace, generation,
submission timestamp, maximum turns and catalog workload. Model proposals and
execution results remain mutable protocol projections outside that input snapshot.
Shared input drift refuses new approval, execution, model observation/publication
and recovery with `E_OUTWARD_AUTHORITY_INPUT_DRIFT`. Existing exact effect bindings,
claim/intent/observation states and recovery fences remain independently required.

The shared attempt enters execution when governed execution, handoff admission or
direct approval preparation begins. Waiting for an outward tool approval remains
an explicit protocol cursor within that bounded attempt; it does not mint another
control-plane attempt or implicitly authorize recovery.

## Terminal authority and projections

`outward_terminal_service.publish_outward_terminal` is the sole outward terminal
publisher. It validates retained evidence and calls `ControlPlanePublicationService`
to create shared final truth. The same transaction closes the shared run/attempt,
retains a terminal step with receipt references, and commits the outward projection
and terminal event. That event binds the full final-truth digest.

| Outcome | Protocol status | Shared result | Evidence |
|---|---|---|---|
| All admitted tool steps succeed | `completed` | `success` | Every approved binding, observed receipt and shared effect-journal entry validates |
| Operator denies approval | `completed` | `blocked` | Retained denial and decision event |
| Approval expires | `failed` | `blocked` | Retained expiry and decision event |
| Connector policy or trust handoff rejects | `completed` | `blocked` | Retained rejection event |
| Model/tool execution fails or turn budget ends early | `failed` | `failed` | Retained model result or observed effect receipt; unresolved residual uncertainty is preserved |

Denial triggers the runtime's terminal stop policy. An approval denial is not
silently converted into a separate operator `MARK_TERMINAL` command. Denial and
expiry now close atomically with their decisions; the old denial continuation
performs no terminal writes. Completed protocol status alone never establishes
successful execution or broader objective quality.

Authenticated run submission, status, list and summary project `authority_state`
and `final_truth` from the shared records. Missing or contradictory shared truth
cannot produce a successful final result. The status projection checks its digest
against the committed terminal event. Existing witness/ledger protocols retain
their stated scope; a tool-sequence receipt does not establish CAP-1 objective
verification, arbitrary remote-effect idempotence or hostile containment.

## Historical admission boundary

Generation-zero history remains quarantined. Earlier generation-one runs without
shared admission remain inspectable as `authority_state=migration_required`, with
no fabricated final truth. Execution/recovery requires explicit authority migration;
automatic expiry skips that history. Ordinary submission cannot backfill a missing
initial event or adopt current mutable rows as original admission evidence.

`python -m orket.interfaces.outward_authority_cli --db <path> --run-id <id> --inspect`
returns the retained-run digest and validated ledger anchor without adopting it.
After reviewing the current inputs and stopping old owners, invoke the same
command with `--expected-run-digest <digest> --actor-ref <operator> --owners-stopped`.
Changed reviewed state refuses adoption. This attestation does not stop or fence
arbitrary legacy executables; operators must keep old writers stopped.

The migration borrows the owning writer connection to validate the retained
ledger, including schema migrations in that transaction, then checks the admission event, available exact
bindings, effect journal and terminal evidence. One transaction appends a named
current-state adoption event and common admission. For terminal histories, the
same publisher validates evidence and appends `outward_final_truth_adopted`.
It does not reconstruct an old terminal event or rewrite the historical protocol
run, proposal, model admission, effect, recovery fence or workspace/target path.
The adoption event is the new snapshots' source and admission receipt. An identical
retry validates that receipt and the old ledger prefix without writing again.

Source CLI proof covers copies of old installed success, denial, expiry and policy
rejection, plus pending approval, ready/claimed/observed model work and
claimed/observed/dispatching effects. This proves migration and repeat preservation;
it does not authorize redispatch. A separate source application proof continues
fresh old-wheel histories: ready model work runs once, observed model results
are reused, claimed model/effect work requires explicit fenced recovery, observed
effects publish without invocation, and uncertain dispatch remains blocked. Model/effect
claim and recovery rules remain independently enforced. Source fault injection
also covers admission rollback and retry. Native process termination at adoption
and terminal publication rolls back both boundaries; explicit retry preserves
history and publishes the shared result. The ledger reader borrows the writer's
connection. A separate read connection caused a retained Windows post-crash
`SQLITE_IOERR_TRUNCATE` counterexample; the shared-connection path passes the same
native cases. This does not establish generic filesystem or host-failure recovery.
Installed Windows/Linux Python 3.11/3.12 now also pass 11 copied migration cases
and seven continuation cases each, using freshly executed old-wheel histories.
The isolated old installation shares the selected interpreter's dependencies;
this is an old-core migration boundary, not an old dependency-stack certification.
The 410-case source and four-cell installed regression envelope passes, and actual
installed llama.cpp success, denial, expiry and policy rejection agree with shared
final truth. Retained hash verification is separate from execution success; Linux
proof roots use the persistent cache after the first temporary roots disappeared.
The canonical plan records artifact identities and the acceptance audit. Unknown
legacy terminal shapes remain refused. Card/common-family conformance and the
later architectural/capability gates remain open.
