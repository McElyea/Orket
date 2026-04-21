# Orket NorthStar Governed Change Packets Implementation Plan

Last updated: 2026-04-19
Status: Completed and archived
Owner: Orket Core

Accepted requirements: `docs/projects/archive/northstar-governed-change-packets/NGCP04192026-LANE-CLOSEOUT/ORKET_NORTHSTAR_GOVERNED_CHANGE_PACKETS_REQUIREMENTS_V1.md`

Primary durable authority dependencies:

1. `CURRENT_AUTHORITY.md`
2. `docs/specs/GOVERNED_CHANGE_PACKET_TRUSTED_KERNEL_V1.md`
3. `docs/specs/GOVERNED_CHANGE_PACKET_V1.md`
4. `docs/specs/GOVERNED_CHANGE_PACKET_STANDALONE_VERIFIER_V1.md`
5. `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md`
6. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`

Guide and reference dependencies:

1. `docs/guides/GOVERNED_REPO_CHANGE_PACKET_GUIDE.md`

Archive and history references:

1. `docs/projects/archive/governed-change-packet/GCP04192026-LANE-CLOSEOUT/CLOSEOUT.md`

## Purpose

Implement the first NorthStar expansion increment after the governed repo-change packet closeout.

This lane does not broaden Orket's trust boundary. It productizes and hardens the existing `trusted_repo_config_change_v1` governed change packet so an outside operator can run, inspect, and trust the current packet path with less implicit repo knowledge.

## Bounded Scope

This implementation increment is limited to:

1. the existing `trusted_repo_config_change_v1` packet family
2. the existing `governed_change_packet.v1` packet schema
3. the existing standalone verifier surface
4. the existing staged adversarial benchmark corpus
5. operator guidance and diagnostics for the current packet path

This lane must not:

1. admit a second packet family
2. publish the staged benchmark without explicit approval
3. claim replay determinism or text determinism
4. make provider-backed governed-proof paths externally admitted
5. turn packet projections, logs, approvals, dashboards, or summaries into proof authority

## NorthStar Outcome

The intended operator outcome is:

```text
An outside operator can generate the repo-change packet, inspect its authority
manifest, run the standalone verifier, understand any downgrade or rejection,
and compare the result against the staged adversarial corpus without trusting
Orket narration first.
```

The strongest allowed claim ceiling for this implementation increment remains `verdict_deterministic`.

## Workstream 0 - Authority Handoff

### Goal

Move the accepted requirements out of future incubation and make this implementation plan the active roadmap authority.

### Tasks

1. keep the active roadmap entry pointed at this implementation plan
2. keep the accepted requirements as a companion document, not active execution authority
3. add the active project folder to the Project Index
4. ensure the retired future-incubation requirements path is not used as active roadmap authority

### Exit criteria

1. docs project hygiene passes
2. the roadmap `Priority Now` entry points to this implementation plan
3. the Project Index includes `northstar-governed-change-packets`

### Current checkpoint

Completed on 2026-04-19 before final archive while the following were true:

1. accepted requirements moved out of future incubation
2. the roadmap `Priority Now` entry pointed to this implementation plan while the lane was active
3. docs project hygiene passed with `northstar-governed-change-packets` in the Project Index before closeout

## Workstream 1 - Operator Packet Path Productization

### Goal

Reduce the amount of internal repo knowledge required to run and inspect the existing packet.

### Tasks

1. review the current packet generation and verifier commands for avoidable friction
2. decide whether to add a thin operator wrapper or improve the existing scripts and guide
3. make default workspace behavior explicit and safe for sequential and parallel runs
4. ensure packet output points operators to authority-bearing artifacts, not projection-only summaries
5. update `docs/guides/GOVERNED_REPO_CHANGE_PACKET_GUIDE.md` with the final operator path

### Exit criteria

1. the positive packet path remains live and fixture-bounded
2. the operator guide gives one primary command path and one verifier command path
3. no stronger trust claim is introduced

### Required proof

```text
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_governed_repo_change_packet.py
python scripts/proof/verify_governed_change_packet.py --input benchmarks/results/proof/governed_repo_change_packet.json --output benchmarks/results/proof/governed_repo_change_packet_verifier.json
```

Expected observed result:

1. packet path: `observed_result=success`, `claim_ceiling=verdict_deterministic`
2. verifier path: `observed_result=success`, `packet_verdict=valid`, `claim_tier=verdict_deterministic`

### Current checkpoint

Completed on 2026-04-19 for the existing `trusted_repo_config_change_v1` packet path:

1. the existing packet wrapper remains the primary operator command
2. the benchmark default workspace is separate from the primary packet workspace
3. the guide names one packet command and one verifier command
4. packet output points to authority-bearing artifacts and support-only projections separately

## Workstream 2 - Standalone Verifier Auditability

### Goal

Make the standalone verifier easier to audit without increasing its trusted computing base.

### Tasks

1. inspect verifier output for missing diagnostics around required roles, authority refs, and claim downgrades
2. keep verifier outcomes limited to `valid`, `invalid`, and `insufficient_evidence`
3. keep the existing offline claim ladder as the claim-tier authority
4. preserve and prove verifier non-interference
5. add focused tests only where they prove fail-closed behavior or clearer diagnostics

### Exit criteria

1. verifier output explains why packets are accepted, downgraded, or rejected
2. verifier checks still resolve to authority-bearing artifacts
3. verifier non-interference remains structurally proved

### Required proof

```text
python scripts/proof/verify_trusted_run_proof_foundation.py
python -m pytest -q tests/scripts/test_governed_change_packet.py tests/scripts/test_trusted_run_proof_foundation.py
```

Expected observed result:

1. proof foundation: `observed_result=success`
2. focused tests: pass

### Current checkpoint

Completed on 2026-04-19:

1. verifier output includes `required_role_diagnostics`, `authority_ref_diagnostics`, and `claim_diagnostics`
2. verifier outcomes remain limited to `valid`, `invalid`, and `insufficient_evidence`
3. verifier stable-digest drift, role drift, missing refs, and unsupported higher claims fail closed
4. non-interference proof now covers the packet verifier, CLI, packet contract helper, and trusted-kernel helper

## Workstream 3 - Staged Benchmark Freshness

### Goal

Keep the adversarial benchmark current and truthfully staged.

### Tasks

1. rerun the current adversarial corpus
2. verify all frozen failure classes still fail closed
3. keep benchmark metadata in `benchmarks/staging/index.json` and `benchmarks/staging/README.md` synchronized
4. do not publish the benchmark without explicit approval
5. record blind spots in the guide or implementation closeout

### Exit criteria

1. six frozen adversarial cases remain caught
2. staging index/readme sync passes
3. the benchmark remains staged unless explicit publication approval is given

### Required proof

```text
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_governed_change_packet_adversarial_benchmark.py
python scripts/governance/sync_published_index.py --index benchmarks/staging/index.json --readme benchmarks/staging/README.md --write
python scripts/governance/sync_published_index.py --index benchmarks/staging/index.json --readme benchmarks/staging/README.md --check
```

Expected observed result:

1. adversarial benchmark: `observed_result=success`, `case_count=6`
2. staging index/readme sync: pass

### Current checkpoint

Completed on 2026-04-19:

1. the six-case adversarial corpus reruns successfully
2. the benchmark remains staged under `benchmarks/staging/`
3. staging index/readme sync passes
4. no publication action was taken

## Workstream 4 - Adoption Surface

### Goal

Explain why Orket is worth choosing using packet evidence rather than rhetoric.

### Tasks

1. update the operator guide or trust spec only if the evidence supports the wording
2. keep the comparator fixed to `workflow + logs + approvals`
3. make supported and unsupported claims explicit
4. ensure operator-facing material names authority-bearing artifacts separately from support-only narrative

### Exit criteria

1. adoption wording remains claim-capped at `verdict_deterministic`
2. no public wording implies proof of arbitrary workflows or the whole runtime
3. the guide makes the verifier, not Orket narration, the claim authority

### Required proof

```text
python scripts/governance/check_docs_project_hygiene.py
```

Expected observed result: pass.

### Current checkpoint

Completed on 2026-04-19:

1. the guide names the verifier report as packet verdict authority
2. supported and unsupported claims remain explicit
3. the comparator remains fixed to `workflow + logs + approvals`
4. wording remains capped at `verdict_deterministic`

## Workstream 5 - Lane Closeout

### Goal

Close or pause the lane without leaving stale active roadmap authority.

### Tasks

1. decide whether the implementation increment closes as shipped or remains active for a bounded follow-on
2. if closed, archive the implementation plan and closeout under `docs/projects/archive/northstar-governed-change-packets/`
3. if follow-on work is needed, create a new explicit roadmap lane or update this plan with a bounded next scope
4. run docs project hygiene before handoff

### Exit criteria

1. roadmap no longer points to obsolete work
2. active project docs do not carry completed or archived status
3. remaining blockers or drift are recorded truthfully

### Required proof

```text
python scripts/governance/check_docs_project_hygiene.py
```

Expected observed result: pass.

### Current checkpoint

Completed on 2026-04-19:

1. this implementation increment closes as shipped
2. the implementation plan, accepted requirements, and closeout are archived under `docs/projects/archive/northstar-governed-change-packets/NGCP04192026-LANE-CLOSEOUT/`
3. the roadmap no longer points to this completed lane
4. remaining limits are recorded in the closeout

## Required Closeout Command Set

Before claiming completion, run this verification and sync command set:

```text
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_governed_repo_change_packet.py
python scripts/proof/verify_governed_change_packet.py --input benchmarks/results/proof/governed_repo_change_packet.json --output benchmarks/results/proof/governed_repo_change_packet_verifier.json
python scripts/proof/verify_governed_change_packet_trusted_kernel.py --output benchmarks/results/proof/governed_change_packet_trusted_kernel_model.json
python scripts/proof/verify_trusted_run_proof_foundation.py
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_governed_change_packet_adversarial_benchmark.py
python scripts/governance/sync_published_index.py --index benchmarks/staging/index.json --readme benchmarks/staging/README.md --write
python scripts/governance/sync_published_index.py --index benchmarks/staging/index.json --readme benchmarks/staging/README.md --check
python -m pytest -q tests/scripts/test_governed_change_packet.py tests/scripts/test_trusted_run_proof_foundation.py tests/scripts/test_first_useful_workflow_slice.py
python scripts/governance/check_docs_project_hygiene.py
```

If the full canonical test command is attempted, report its observed result separately. Do not substitute a timed-out or partial run for the closeout command set above.

## Resolved Decisions

1. Use the existing packet wrapper and improve the verifier, benchmark workspace behavior, and guide rather than adding another wrapper command.
2. Add verifier output fields for required-role diagnostics, authority-ref diagnostics, and claim diagnostics.
3. Keep the adversarial benchmark staged; no publication approval was given.
4. Do not open a hidden follow-on lane. A second packet family, replay determinism, text determinism, or verifier distribution packaging requires a later explicit roadmap lane.
