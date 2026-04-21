# Orket Governed Change Packet Implementation Plan

Last updated: 2026-04-19
Status: Completed and archived
Owner: Orket Core

Closeout authority: `docs/projects/archive/governed-change-packet/GCP04192026-LANE-CLOSEOUT/CLOSEOUT.md`

Accepted requirements: none. This archived plan is historical execution authority only; durable trusted-kernel, packet, and standalone-verifier semantics now live in `docs/specs/GOVERNED_CHANGE_PACKET_TRUSTED_KERNEL_V1.md`, `docs/specs/GOVERNED_CHANGE_PACKET_V1.md`, and `docs/specs/GOVERNED_CHANGE_PACKET_STANDALONE_VERIFIER_V1.md`.
Primary authority dependencies:
1. `CURRENT_AUTHORITY.md`
2. `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
3. `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`
4. `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`
5. `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`
6. `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md`
7. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`
8. `docs/specs/TRUSTED_CHANGE_SCOPE_ADMISSION_STANDARD_V1.md`
9. `docs/specs/TRUSTED_CHANGE_SCOPE_CATALOG_V1.md`
10. `docs/specs/GOVERNED_CHANGE_PACKET_TRUSTED_KERNEL_V1.md`
11. `docs/specs/GOVERNED_CHANGE_PACKET_V1.md`
12. `docs/specs/GOVERNED_CHANGE_PACKET_STANDALONE_VERIFIER_V1.md`
13. `docs/projects/governed-proof/ORKET_PROOF_CARRYING_GOVERNED_CHANGES_IMPLEMENTATION_PLAN.md`

## Authority Relationship

This lane is a follow-on packetization and verifier-productization lane, not a reopening of governed-proof compare-scope selection.

The authority split is:

1. the governed-proof lane remains authoritative for admitted compare-scope selection, internal-versus-public admission posture, and any future publication-boundary widening,
2. this lane is authoritative only for packaging the already externally admitted repo-change slice into the first outside-operator Governed Change Packet and for the trusted-kernel plus standalone-verifier work needed to support that packet, and
3. any later packetization of a newly admitted compare scope or any broader public-trust update must still synchronize same-change authority with the relevant governed-proof and trust-boundary specs.

## Bootstrap Posture

This lane is intentionally starting before a separate accepted-requirements packet exists, but that bootstrap posture is temporary and bounded.

The extraction rule is:

1. Workstream 1 must extract the trusted-kernel contract into durable spec authority,
2. Workstream 2 must extract the packet and standalone-verifier contracts into durable spec authority, and
3. after those specs exist, this plan must stop acting as the sole authority for kernel semantics, packet schema, or verifier semantics and must defer to the extracted durable specs.

## Purpose

Ship one independently verifiable Governed Change Packet that an outside operator can run, inspect, and trust without trusting Orket first.

The packet is not meant to prove all of Orket. It is meant to prove one bounded change strongly enough that:
1. a skeptical evaluator can inspect the packet without reading the whole codebase,
2. a standalone verifier can cap the allowed claim tier from packet evidence alone, and
3. Orket can show a concrete trust advantage over workflow plus logs plus approvals.

This lane governs:
1. formalizing the smallest trusted kernel Orket can defend mathematically,
2. shipping a standalone verifier with a smaller trusted computing base than the main runtime,
3. packaging one flagship workflow end to end as a Governed Change Packet,
4. publishing adversarial failure benchmarks that distinguish Orket from workflow-plus-logs proof theater, and
5. making the comparative adoption case for why Orket is worth choosing.

This lane does not, by itself:
1. claim full mathematical proof of the entire Python runtime,
2. broaden the current external trust slice without same-change evidence and authority updates,
3. treat runtime logs, approvals, or observability alone as independent verification, or
4. attempt a many-workflow launch before one workflow is externally legible and independently verifiable.

## North Star

The north-star operator outcome for this lane is:

```text
Given one Governed Change Packet, a skeptical outside operator can verify in
minutes that the change was authorized, bounded, validator-backed, effect-lined,
uniquely finalized, and claim-capped without trusting Orket first.
```

The corresponding product claim this lane is trying to earn is:

```text
Orket packages one bounded governed change into independently verifiable execution truth.
```

These statements are lane success targets only. They are not durable public trust wording unless the trust and publication authorities are updated in the same change that proves them.

## Governing Decisions

The following decisions govern this lane unless later accepted requirements replace them:

1. Orket must make only bounded mathematical-soundness claims over a small trusted kernel with explicit invariants, not over the entire runtime.
2. The standalone verifier must be independently runnable and easier to audit than the main Orket runtime path it verifies.
3. The flagship packet must fail closed when required authority, effect lineage, or final-truth evidence is missing or contradictory.
4. The first externally useful packet must prove one bounded workflow better than generic workflow telemetry, not many workflows vaguely.
5. Comparative trust claims must be grounded in concrete adversarial failure cases that Orket catches and a workflow-plus-logs-plus-approvals baseline does not.
6. Public-facing adoption claims must stay capped at the strongest independently checkable claim the packet and verifier can actually support.
7. Existing admitted compare-scope authority should be reused where possible instead of inventing a parallel proof vocabulary.
8. The first flagship packet should avoid external provider dependence when a locally verifiable bounded workflow can answer the same trust question more directly.
9. The packet may become the primary operator entry artifact, but all claim-bearing checks must still resolve to the underlying authority artifacts and verifier outputs rather than to packet projections alone.

## Flagship Workflow Freeze

This lane freezes the first flagship packet target as:

1. compare-scope family: `trusted_repo_config_change_v1`
2. packet working name: Governed Repo Change Packet v1
3. bounded workflow question:

```text
Can Orket prove one governed repo config change strongly enough that an outside
operator can inspect the packet, run a standalone verifier, and reject overclaim
without trusting Orket first?
```

### Why this workflow is selected

This lane chooses the repo-change slice because it is currently the best foundation for an outside-operator packet:

1. it already has the only externally admitted trust slice in `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`,
2. it already has a witness bundle, campaign report, validator surface, and offline verifier path,
3. it avoids Bedrock, cloud quota, or provider availability blockers,
4. it is easier for an outside evaluator to run locally than Terraform provider-backed proof, and
5. it is legible enough to demonstrate the trust difference between bounded proof and workflow-plus-logs.

### Why the other current candidates are not first

1. `trusted_terraform_plan_decision_v1` is useful, but it is not yet part of the externally admitted trust slice, its truthful operator path currently depends on provider-backed publication readiness, and it is less locally reproducible for a first outside-operator packet than the repo-change slice.
2. `trusted_run_productflow_write_file_v1` is a strong internal authority slice, but it is currently less legible as the first outside-operator packet than the repo-change slice and still carries more internal-product context than the repo-change evaluator path.

## Packet v1 Boundary

The first Governed Change Packet v1 is bounded to one local repo config mutation over one declared target artifact.

The packet must prove:

1. the requested target was declared before execution,
2. the approval resolution authorized the bounded mutation,
3. reservation or lease authority covered the target path,
4. the effect journal records the bounded write with no unresolved uncertainty,
5. the deterministic validator checked the final artifact,
6. final truth is present and non-contradictory, and
7. the standalone verifier refuses stronger claims when replay, text identity, or other future evidence is missing.

The packet must not claim:

1. arbitrary repo changes are covered,
2. replay determinism,
3. text determinism,
4. mathematical soundness of the whole runtime, or
5. trust in logs, graphs, review packages, or Packet projections alone.

The packet may be the primary operator artifact for this lane, but it must remain an entry surface over authority-bearing artifacts rather than a substitute authority surface.

## Trusted-Kernel Boundary Freeze

The smallest trusted kernel this lane will try to formalize is:

1. governed input identity,
2. resolved policy and configuration identity,
3. approval binding,
4. reservation and lease authority over the bounded target,
5. checkpoint acceptance before effect,
6. effect publication and lineage,
7. deterministic validator result,
8. final-truth publication and uniqueness,
9. witness-bundle completeness for the bounded claim, and
10. verifier non-interference.

The lane's mathematical claim must stop at this boundary.

It is explicitly out of scope to formally prove:

1. the whole Python runtime,
2. all adapters and integrations,
3. UI behavior,
4. general model correctness, or
5. general workflow determinism beyond the admitted packet boundary.

## Packet Acceptance Question

The outside-operator acceptance question for this lane is:

```text
If I did not trust Orket yet, would this packet plus verifier give me stronger
reason to trust one bounded change than a workflow system that only gave me logs,
approval rows, and output files?
```

This lane is successful only if the answer becomes "yes" for the flagship packet.

## Comparative Baseline Freeze

The baseline comparator for this lane is:

```text
workflow + logs + approvals
```

For this lane, that baseline means:

1. execution logs,
2. approval request and response records,
3. output artifacts,
4. dashboards, traces, graphs, or summaries derived from those records, and
5. no independently claim-capping verifier over a bounded authority packet.

Orket only wins this lane if it can show concrete failure classes where:

1. the baseline still looks success-shaped or ambiguous, but
2. the Governed Change Packet plus standalone verifier fails closed.

## Workstream Order

## Workstream 0 - Packet Target, Boundary, And Adoption Freeze

### Goal

Turn the north-star direction into one bounded execution lane with one flagship packet target and one clear adoption question.

### Tasks

1. freeze the flagship workflow selection to the governed repo-change slice
2. freeze the packet v1 boundary, trusted-kernel boundary, and baseline comparison in this plan
3. define the outside-operator acceptance question and claim ceiling target
4. define the packet components that must exist before the verifier can be considered standalone
5. keep roadmap and project-index authority synchronized

### Exit criteria

1. exactly one flagship workflow is selected
2. the packet boundary and verifier boundary are explicit enough to implement without reopening the lane purpose
3. the lane remains execution-scoped rather than idea-scoped

### Current checkpoint

Completed on 2026-04-19 while all of the following remain true in current repo authority:

1. the flagship packet target remains the repo-change slice built from `trusted_repo_config_change_v1`
2. the packet must answer the bounded repo-change trust question above
3. the mathematical claim boundary remains the small trusted kernel frozen in this plan
4. the lane continues to compare Orket against workflow plus logs plus approvals rather than against a vague "other runtimes" bucket
5. this lane continues to packetize the already externally admitted repo-change slice and does not supersede governed-proof authority over compare-scope selection or publication posture

## Workstream 1 - Formalize The Trusted Kernel

### Goal

Make Orket's strongest mathematical claim rest on one bounded kernel that can be independently checked.

### Tasks

1. extract the trusted-kernel contract into durable authority under `docs/specs/`
2. define the kernel state machine, state variables, transitions, and safety invariants
3. choose one machine-checkable model surface such as TLA+, PlusCal, or Alloy
4. machine-check the kernel properties at least for:
   - no effect without accepted authority
   - no successful final truth without validator and effect evidence
   - no contradictory final truth for one bounded packet
   - no lease or reservation reuse after invalidation
   - verifier path is inspection-only
5. map the existing repo-change proof evidence fields onto the formal kernel model
6. make every uncovered assumption explicit as a machine-readable limitation rather than implicit trust in the runtime

### Exit criteria

1. the trusted kernel is specified as a bounded formal contract
2. the key kernel safety properties are machine-checked or independently checkable
3. the mathematical claim boundary is explicit and narrow enough to defend publicly
4. the repo-change packet can point to formal-kernel conformance instead of only implementation detail

### Planned durable outputs

The preferred outputs for this workstream are:

1. `docs/specs/GOVERNED_CHANGE_PACKET_TRUSTED_KERNEL_V1.md`
2. one machine-checkable model file under a durable repo path chosen in the same change
3. one proof or conformance artifact linking packet evidence fields to kernel state

### Current checkpoint

Completed on 2026-04-19 for the admitted repo-change packet boundary:

1. the durable trusted-kernel contract now lives in `docs/specs/GOVERNED_CHANGE_PACKET_TRUSTED_KERNEL_V1.md`
2. the bounded machine-checkable model now writes `benchmarks/results/proof/governed_change_packet_trusted_kernel_model.json` through `python scripts/proof/verify_governed_change_packet_trusted_kernel.py`
3. the packet now carries a kernel-conformance projection over the admitted evidence rows
4. the kernel claim remains explicitly bounded to `trusted_repo_config_change_v1`

## Workstream 2 - Ship The Standalone Verifier

### Goal

Ship a verifier that can validate a Governed Change Packet without trusting the full Orket runtime.

### Tasks

1. define the Governed Change Packet schema and verifier input contract
2. choose whether the standalone verifier is:
   - a new smaller verifier surface built over the existing witness bundle and offline-verifier contract family, or
   - an extracted wrapper over the current offline verifier plus packet contract checks with a smaller trusted computing base
3. implement a standalone verifier entrypoint that does not depend on hidden runtime state, live services, or mutable repo-global state
4. make verifier outcomes fail closed as:
   - `valid`
   - `invalid`
   - `insufficient_evidence`
5. preserve current claim-ladder discipline from `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`
6. package the verifier so an outside operator can run it without reconstructing the whole Orket dev environment
7. prove verifier non-interference on the admitted verification path

### Standalone verifier outcome mapping

The standalone verifier outcomes below are transport-level packet verdicts, not replacement claim tiers for the existing offline-verifier ladder.

1. `valid` means the packet structure, authority linkage, and required evidence references pass packet-level checks; claim assignment then proceeds through the existing offline-verifier claim ladder.
2. `invalid` means the packet is contradictory, tampered, or authority-mismatched; no claim is allowed.
3. `insufficient_evidence` means the packet is structurally coherent but does not carry enough linked authority evidence for the requested packet claim; lower claims may be preserved or downgraded only if the existing offline-verifier claim ladder allows them.

### Exit criteria

1. the standalone verifier can validate at least one live packet end to end
2. the verifier trusted computing base is smaller and more auditable than the main runtime path
3. verifier output truthfully caps the claim ceiling instead of mirroring Orket's preferred story
4. the verifier can reject or downgrade at least one malformed or incomplete packet without consulting hidden runtime state

### Planned durable outputs

The preferred outputs for this workstream are:

1. `docs/specs/GOVERNED_CHANGE_PACKET_V1.md`
2. `docs/specs/GOVERNED_CHANGE_PACKET_STANDALONE_VERIFIER_V1.md`
3. one canonical verifier command and one stable verifier output family

### Current checkpoint

Completed on 2026-04-19 for the admitted repo-change packet family:

1. the packet schema now lives in `docs/specs/GOVERNED_CHANGE_PACKET_V1.md`
2. the standalone verifier contract now lives in `docs/specs/GOVERNED_CHANGE_PACKET_STANDALONE_VERIFIER_V1.md`
3. the canonical verifier command is now `python scripts/proof/verify_governed_change_packet.py --input benchmarks/results/proof/governed_repo_change_packet.json --output benchmarks/results/proof/governed_repo_change_packet_verifier.json`
4. the verifier remains inspection-only and is now part of the structural proof-foundation non-interference inspection surface

## Workstream 3 - Package One Flagship Workflow End To End

### Goal

Turn the governed repo-change slice into the first Governed Change Packet v1.

### Tasks

1. define the packet manifest for the repo-change slice, including:
   - operator-readable summary
   - authority artifact refs
   - effect and validator refs
   - final-truth ref
   - witness and claim-verifier refs
   - explicit limitations
2. decide whether the packet is emitted:
   - directly by the repo-change proof workflow, or
   - by a packet builder over the existing witness-bundle artifact family
3. ensure the packet is the primary operator artifact and not just another support summary
4. connect the packet to the formal kernel boundary and standalone verifier
5. write the outside-operator walkthrough for:
   - generate packet
   - inspect packet
   - run standalone verifier
   - inspect at least one negative proof packet
6. run the real path and record observed path and observed result truthfully

### Exit criteria

1. one repo-change workflow emits a live Governed Change Packet
2. an outside operator can inspect the packet and run the standalone verifier
3. the packet claim ceiling is supported by actual evidence rather than presentation alone
4. the packet clearly distinguishes authority-bearing artifacts from support-only narrative material

### Planned durable outputs

The preferred outputs for this workstream are:

1. one canonical packet artifact path for the repo-change workflow
2. one evaluator guide dedicated to the Governed Change Packet path
3. at least one positive packet and one negative packet artifact family

### Current checkpoint

Completed on 2026-04-19 for the first flagship packet:

1. `python scripts/proof/run_governed_repo_change_packet.py` now emits `benchmarks/results/proof/governed_repo_change_packet.json`
2. the packet path regenerates the positive live proof, campaign report, offline verifier report, and negative proofs needed for the admitted slice
3. `docs/guides/GOVERNED_REPO_CHANGE_PACKET_GUIDE.md` is now the dedicated outside-operator walkthrough for the packet path
4. the packet manifest explicitly distinguishes primary authority, authority-bearing, negative-proof, and entry-projection rows

## Workstream 4 - Publish Adversarial Failure Benchmarks

### Goal

Demonstrate what Orket catches that workflow plus logs plus approvals does not.

### Tasks

1. define an adversarial failure corpus for the flagship packet that includes at least:
   - wrong target artifact with superficially valid approval
   - success-shaped packet with missing validator
   - success-shaped packet with missing effect evidence
   - contradictory final truth
   - packet overclaim beyond available evidence
   - projection-only material presented as authority
2. define the baseline comparison artifact family for workflow plus logs plus approvals
3. publish benchmark artifacts under the correct staged or published benchmark authority path
4. prove the standalone verifier and packet contract fail closed on the adversarial set
5. make benchmark blind spots explicit instead of leaving them implied

### Exit criteria

1. at least one benchmark corpus exists that is legible to outside evaluators
2. the benchmark shows concrete failure classes where Orket's packet plus verifier story is stronger than the baseline
3. benchmark publication does not overclaim beyond the verified corpus
4. the verifier catches at least one case where logs plus approval plus output artifact would still look plausibly successful

### Current checkpoint

Completed to staged-candidate level on 2026-04-19:

1. the initial adversarial corpus now lives in `benchmarks/staging/General/governed_repo_change_packet_adversarial_benchmark_2026-04-19.json`
2. the corpus covers the six frozen failure classes in this plan
3. the benchmark remains staged rather than published because no explicit publication approval has been given

## Workstream 5 - Comparative Trust Case And Adoption Surface

### Goal

Answer why anyone should choose Orket with proof rather than rhetoric.

### Tasks

1. define the operator-facing adoption claim for the flagship packet
2. publish the comparative case against workflow plus logs plus approvals using the adversarial benchmark evidence
3. define the minimal outside-operator runbook for packet generation, inspection, and verification
4. update durable trust or packet specs only if the evidence supports the stronger story
5. decide truthfully whether the lane:
   - closes as shipped,
   - splits into a follow-on lane for the next workflow packet, or
   - remains active because the first packet still fails the outside-operator trust question

### Exit criteria

1. the adoption case is evidence-backed and externally legible
2. the operator path from run to packet to verifier is short and truthful
3. Orket can show why the packet is stronger than workflow plus logs plus approvals without broadening into unsupported product claims
4. the lane can either close or split cleanly into follow-on lanes without leaving the North Star vague again

### Current checkpoint

Completed for the current admitted external slice on 2026-04-19:

1. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md` now admits the packet and standalone packet verifier as part of the current bounded repo-change trust story
2. the operator path from packet generation to packet verification is now frozen in `docs/guides/GOVERNED_REPO_CHANGE_PACKET_GUIDE.md`
3. the comparative trust case remains explicitly capped at the fixture-bounded `trusted_repo_config_change_v1` slice and `verdict_deterministic`

## Sequencing Rules

The workstreams must execute in this order unless a later same-change authority update records a narrower dependency graph:

1. Workstream 0 is frozen first and complete.
2. Workstream 1 must define the trusted-kernel claim boundary before Workstream 5 can publish any stronger adoption story.
3. Workstream 2 and Workstream 3 may overlap once the packet schema and verifier input contract are frozen.
4. Workstream 4 must execute before Workstream 5, because the comparative trust case depends on adversarial benchmark evidence.
5. Workstream 5 must not broaden the current external trust boundary unless same-change evidence and durable trust authority support it.

## Comparative Success Conditions

This lane only succeeds if the first packet can demonstrate all of the following:

1. stronger than logs:
   the packet contains authority-bearing evidence rather than merely narrated workflow history
2. stronger than approvals:
   the verifier checks that the approved target, actual effect, validator input, and final truth still align
3. stronger than output files:
   the packet and verifier reject success-shaped output when required authority or effect evidence is missing
4. stronger than Orket self-assertion:
   the standalone verifier can independently downgrade or block claims from packet evidence alone

## Strategic Completion Gate

This lane can close only when all of the following are true:

1. the trusted kernel is formally specified and machine-checked or independently checkable over its admitted boundary
2. the standalone verifier can validate the flagship packet without depending on hidden runtime state
3. one flagship repo-change workflow emits a Governed Change Packet end to end
4. adversarial benchmarks exist and demonstrate concrete trust advantages over workflow plus logs plus approvals
5. the operator story is externally useful, inspectable, and claim-capped by actual verifier evidence
6. the resulting trust reason can still be stated without implying proof of the whole runtime

## Planned Outputs

This lane is expected to produce:

1. a bounded trusted-kernel formal contract under `docs/specs/`
2. a Governed Change Packet schema and standalone verifier surface
3. one flagship Governed Repo Change Packet workflow
4. adversarial benchmark artifacts proving where Orket is stronger than workflow plus logs plus approvals
5. a truthful comparative adoption surface for outside operators

## Current Lane Posture

As of 2026-04-19, the lane stands in this truthful position:

1. the repo-change slice is already the only externally admitted trust slice and therefore is the correct foundation for the first packet,
2. the packet, standalone verifier, and trusted-kernel contract now exist as durable repo authority for that admitted slice,
3. the current packet path is still fixture-bounded and does not broaden the external trust boundary beyond `trusted_repo_config_change_v1`,
4. the adversarial benchmark now exists as a staged candidate and not yet as a published benchmark, and
5. the active lane is closed; future expansion or follow-on packet families must reopen through a new explicit roadmap lane.
