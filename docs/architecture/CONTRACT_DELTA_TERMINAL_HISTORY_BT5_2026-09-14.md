# Terminal history consistency

- Owner: Orket Core, architectural-truth BT-5.3–5.
- Date: 2026-09-14.
- Status: candidate; focused and expanded source repair passes; installed acceptance remains open.
- Contracts: `docs/specs/CONTROL_PLANE_TERMINAL_AUTHORITY.md`, `docs/specs/GOVERNED_AGENT_LOOP_V1.md`.

The preserved split history exposed successful final truth beside an unfinished
run and attempt. Reentry trusted the run reference without validating that join;
replay did not load an unreferenced truth. The shared repository also accepted
multiple final-truth identities for a run and selected one by lexical ordering.

The shared repository now retains one immutable truth per run and refuses
ambiguous historical reads. The common domain validator checks the terminal
join. Governed-agent inspection and replay consume one existing history snapshot;
reentry checks under the transaction owner before work. Parent run/attempt
admission is atomic. The duplicated inspection execution/truth ports are removed
from production and test composition. The oversized record repository shrinks by
moving its final-truth storage operations into one focused adapter module.

Historical contradictions remain preserved and unadmitted. There is no schema
rewrite, automatic reconciliation or redispatch. Healthy response shapes and
recorded-decision replay scope remain unchanged; conflicting inspection returns
HTTP 409 or nonzero CLI status. See the contract for the bounded claim and rollback.

The corrected source counterexample has 17 failures and five controls. The first
repair passes 69 focused cases using real SQLite and child processes with
controlled inference. The first test version additionally rejected two already
adequate replay diagnostic strings; those two failures were test assertions, not
new runtime defects. All original observations and copied databases remain under
`.tmp/bt5-family-history/`. A further 58 source cases pass, including authenticated
API refusal, two native writer processes and interrupted parent admission. The
shared outward/cards/agent envelope passes 55 cases with controlled inference.
These overlapping selections are separate scopes, not additive coverage.

The previously installed 7558b9c7 core wheel reproduces all three added negative
controls: both competing truths are accepted, interrupted attempt admission leaves
a parent run, and inconsistent API inspection returns HTTP 200. The retained
foreign-harness report records three failures and no collection errors or skips.
Fresh installed and provider proof must bind the new candidate before acceptance.

The first 12a376ab wheel is unaccepted. Its 1,041-case source/Windows envelopes
pass, but Linux has seven assertions looking under uppercase `ISSUE-1` while the
writer's retained directory is lowercase `issue-1`. A persistent Linux repeat
confirms seven failures and nine controls, with the actual lowercase artifacts.
The test paths now match the existing convention and the oversized file shrinks.

Additional installed proof exposed two runtime gaps: a 64 MiB final-truth payload
bypassed the replay bound, and the real llama.cpp wake flow failed after renewal
hit a database lock (seven other provider cases passed). A deterministic shared
repository control reproduces the authority-read/renewal lock cycle; its separate
reader control passes. Claim validation now reads committed state without the
renewal lock, and the canonical truth reader accepts the caller's byte bound.
The repaired focused envelope passes 70 cases. Original fixture-construction and
probe-directory setup mistakes are retained separately from runtime failures.

The corrected d77cd7e3 candidate passes 1,044 cases in source, Windows 3.11/3.12
and Linux 3.12. Linux 3.11 has 1,043 passes and one SDK frame-timeout failure in
the effect-resume positive fixture. No errors or skips occur. Actual installed
llama.cpp now passes all eight cases, and native terminal interruption/retry and
historical CLI refusal pass on all four platforms. The corrected candidate is
still unaccepted pending diagnosis of that frame timeout; passing other cells
does not establish its cause. The canonical plan records exact evidence and the
persistent-fixture diagnostic needed next at that checkpoint.

The subsequent startup control retains the original eight/seven-second request
and lease limits, uses the production handshake default for positive proof and
explicitly verifies two-second expiry without final truth. The 1,046-case source
and Linux 3.11 envelopes pass. Windows fixture path quoting caused one Git failure
per cell; corrected seven-case admission follow-ups pass on unchanged test bytes.
Linux 3.12 exposes a separate non-atomic turn-tool closeout: reversed wall-clock
publication leaves successful terminal records beside an active lease. The clock
reversal's cause is unknown. Current acceptance remains open for that demonstrated
runtime gap, with retained fixtures in `gate-startup/`; the timestamp rule is not
relaxed. Separate composed controls expose interrupted cards parent admission.
