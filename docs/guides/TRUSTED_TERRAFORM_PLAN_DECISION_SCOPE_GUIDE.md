# Trusted Terraform Plan Decision Scope Guide

Last reviewed: 2026-04-19

Use this guide to inspect the admitted internal Terraform governed-proof scope without inferring that it is already part of the public trust slice.

## Current Truth

- Admitted internal compare scope: `trusted_terraform_plan_decision_v1`
- Current status: internally admitted, not externally publishable
- Current truthful claim ceiling: `verdict_deterministic`
- Current proof posture: implemented and live-proven for internal governed-proof evaluation
- Reused runtime authority: `docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md`
- Current governed-proof surfaces: live proof command, runtime-backed governed proof command, no-spend live setup packet, no-spend live setup preflight, campaign report, validator report, witness bundle, offline verifier report, publication-readiness gate, and one-shot publication gate sequence
- Current publication blocker: admitted successful campaign evidence still comes from the bounded local harness, while the provider-backed governed proof path is not yet admitted public evidence and the readiness gate must fail closed

The current repo truth is that Orket has already shipped a Terraform plan reviewer contract and supporting proof for that workload, and the governed-proof lane now wraps one bounded Terraform plan review decision with admitted internal trusted-run proof. That internal admission does not, by itself, widen the public trust/publication story.

## Run The Current Evaluator Path

1. Inspect the chosen scope contract:

```text
docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md
```

Expected result: the scope identity, mutation boundary, required authority families, must-catch set, and active proof surfaces are explicit.

2. Inspect the reused runtime contract:

```text
docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md
```

Expected result: Terraform reviewer verdict, capability, publication, and audit boundaries are explicit and remain narrower than infrastructure mutation.

3. Run or inspect the governed-proof entrypoints for this compare scope:

```text
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_terraform_plan_decision.py
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_terraform_plan_decision_campaign.py
python scripts/proof/run_trusted_terraform_plan_decision_runtime_smoke.py --output benchmarks/results/proof/trusted_terraform_plan_decision_live_runtime.json
python scripts/proof/verify_offline_trusted_run_claim.py --input benchmarks/results/proof/trusted_terraform_plan_decision_witness_verification.json --claim verdict_deterministic --output benchmarks/results/proof/trusted_terraform_plan_decision_offline_verifier.json
python scripts/proof/prepare_trusted_terraform_live_setup_packet.py
python scripts/proof/check_trusted_terraform_live_setup_preflight.py
python scripts/proof/check_trusted_terraform_publication_readiness.py
python scripts/proof/run_trusted_terraform_plan_decision_publication_gate.py
```

Expected result: the first two commands produce the admitted local-harness governed-proof evidence, the runtime-smoke command attempts a provider-backed governed-proof run and must fail closed when required AWS inputs are absent, the live setup packet generates local setup files without AWS calls, the live setup preflight validates local provider configuration without AWS calls, the readiness command reports whether publication widening is blocked, the one-shot gate sequence fails fast on missing live inputs by default and reruns proof steps only when live preflight passes or `--force-local-evidence` is supplied, and none of them by themselves widen the external/public trust slice.

4. Prepare the provider-backed live inputs before expecting publication readiness to pass:

```text
ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI=<s3://bucket/path/to/terraform-plan.json>
ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID=<bedrock-model-id>
AWS_REGION=<region>
```

Expected result: the publication gate sequence reports `live_environment_preflight.status=pass` only when the required non-secret inputs are present. Without those inputs, the default sequence records `execution_mode=preflight_blocked` and skips proof steps. Use `python scripts/proof/run_trusted_terraform_plan_decision_publication_gate.py --force-local-evidence` only when you intentionally want to refresh local artifacts while preserving blocked publication truth. The gate does not inspect or record AWS credential values; credentials must come from the normal AWS provider chain.

Run the no-spend setup preflight before a live attempt:

```text
python scripts/proof/prepare_trusted_terraform_live_setup_packet.py
python scripts/proof/check_trusted_terraform_live_setup_preflight.py
```

Expected result: the setup packet writes `benchmarks/results/proof/trusted_terraform_plan_decision_live_setup_packet.json` plus local files under `workspace/trusted_terraform_live_setup/` without provider calls or credential values. The preflight records `provider_calls_executed=[]`, blocks unreplaced setup-packet S3 placeholders, records the exact planned call set (`S3 GetObject`, `Bedrock Runtime InvokeModel`, `DynamoDB PutItem`), and reports local configuration blockers before credentials or provider APIs are used.

5. Inspect the separate provider-backed runtime smoke seam:

```text
python scripts/reviewrun/run_terraform_plan_review_live_smoke.py --out benchmarks/results/proof/terraform_plan_review_live_smoke.json
```

Expected result: this is the provider-backed runtime smoke seam for the Terraform reviewer contract, distinct from the governed-proof witness commands above. In environments without the required AWS inputs it must fail closed as an environment blocker rather than simulate success.

6. Inspect the current trust/publication boundary:

```text
docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md
CURRENT_AUTHORITY.md
```

Expected result: the current externally admitted public trust slice remains `trusted_repo_config_change_v1`, even though Terraform plan decision is now admitted internally in the governed-proof stack.

## Inspect The Relevant Authority Artifacts

| Artifact | Path | Role |
|---|---|---|
| chosen scope contract | `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md` | durable internal admitted compare-scope authority for the governed-proof lane |
| scope guide | `docs/guides/TRUSTED_TERRAFORM_PLAN_DECISION_SCOPE_GUIDE.md` | truthful evaluator path for the admitted internal scope |
| reusable runtime contract | `docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md` | existing Terraform reviewer runtime boundary reused by the chosen scope |
| provider-backed governed proof path | `scripts/proof/run_trusted_terraform_plan_decision_runtime_smoke.py` | governed-proof wrapper over the provider-backed Terraform reviewer runtime |
| no-spend live setup packet | `scripts/proof/prepare_trusted_terraform_live_setup_packet.py` | local fixture, env template, IAM checklist, and AWS CLI setup command generator that does not call AWS |
| no-spend live setup preflight | `scripts/proof/check_trusted_terraform_live_setup_preflight.py` | local configuration and call-plan check that does not call AWS |
| publication readiness gate | `scripts/proof/check_trusted_terraform_publication_readiness.py` | fail-closed gate that blocks external publication while provider-backed governed-proof evidence is missing |
| publication gate sequence | `scripts/proof/run_trusted_terraform_plan_decision_publication_gate.py` | one-shot gate sequence that reruns prerequisite evidence and preserves readiness status |
| provider-backed runtime smoke seam | `scripts/reviewrun/run_terraform_plan_review_live_smoke.py` | distinct raw runtime smoke path for the Terraform reviewer contract |
| related runbook commands | `docs/RUNBOOK.md` Terraform Plan Reviewer section | existing reviewer verification entrypoints distinct from governed-proof witness commands |
| current public trust boundary | `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md` | shows Terraform plan decision is not yet externally admitted |

Treat the chosen scope contract and current public trust boundary as primary truth. Treat this guide as a support-only evaluator path.

## What This Admission Means

This internal admission means the governed-proof lane now proves:

1. one bounded Terraform plan review decision can be witnessed and verified,
2. deterministic reviewer verdicts remain primary over advisory model text,
3. stronger claims fail closed when the required evidence is missing, and
4. the scope can be evaluated without confusing reviewer runtime authority with public trust publication.

## What This Admission Does Not Mean

This internal admission does not mean:

1. Terraform reviewer live-smoke output is the same thing as the trusted-run witness campaign,
2. the current public trust slice includes Terraform plan decision,
3. the runtime-backed governed proof command is already admitted public evidence,
4. replay determinism or text determinism has been shown for this scope, or
5. Terraform infrastructure mutation is governed-proof verified.
