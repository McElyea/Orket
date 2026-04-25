# NorthStar Disposable AWS Smoke Setup Implementation Plan

Last updated: 2026-04-24
Status: Active - blocked pending explicit live AWS setup/cleanup opt-in
Owner: Orket Core

Primary roadmap authority:
1. `docs/ROADMAP.md`

Dependent lane authority:
1. `docs/projects/northstar-governed-change-packets/ORKET_NORTHSTAR_SECOND_GOVERNED_CHANGE_PACKET_FAMILY_IMPLEMENTATION_PLAN.md`
2. `docs/projects/governed-proof/ORKET_PROOF_CARRYING_GOVERNED_CHANGES_IMPLEMENTATION_PLAN.md`

Durable contract authority:
1. `docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md`
2. `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md`
3. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`

## Purpose

Create a bounded disposable AWS smoke setup path for the NorthStar Terraform public-admission blocker.

The goal is to create or prepare the minimal AWS resources needed to run Orket's existing provider-backed Terraform governed-proof path with truthful live evidence:

1. one private S3 Terraform plan object,
2. one DynamoDB audit table,
3. one admitted Bedrock summary model or inference profile,
4. one generated environment handoff for the existing Orket proof commands,
5. one cleanup path for resources created by this lane.

This lane is preparation and live-smoke enablement only.
It does not publicly admit `trusted_terraform_plan_decision_v1`.
It does not update public trust wording unless the dependent NorthStar admission gates pass in a later same-change admission lane.

## Scope

In scope:
1. generate disposable AWS resource names for a bounded smoke attempt,
2. generate valid Terraform JSON plan fixtures, including randomized but contract-valid resource names and action mixes,
3. upload or prepare upload commands for the selected Terraform plan object,
4. create or prepare creation commands for one pay-per-request DynamoDB audit table keyed by `plan_hash`,
5. set or emit non-secret live inputs for Orket proof commands,
6. run no-spend preflight locally,
7. optionally run the provider-backed runtime smoke when AWS credentials and operator approval are present,
8. always preserve cleanup instructions for created resources.

Out of scope:
1. broad Terraform or AWS infrastructure provisioning,
2. Terraform CLI execution,
3. real infrastructure mutation beyond the smoke S3 object and DynamoDB audit table,
4. public admission of `trusted_terraform_plan_decision_v1`,
5. publication-readiness wording changes,
6. replay-deterministic or text-deterministic claims,
7. credential capture or storage in repo files.

## Active Compare Scope

The only compare scope supported by this setup lane is:

1. `trusted_terraform_plan_decision_v1`

The setup lane does not admit a new compare scope.

## AWS Resource Contract

The disposable live setup must use:

1. S3:
   - one private bucket with a generated or operator-provided globally unique name,
   - one object key, defaulting to `proof/terraform-plan.json`,
   - one Terraform JSON plan object,
   - public access blocked.
2. DynamoDB:
   - one table with a generated or operator-provided name,
   - partition key `plan_hash` of type string,
   - billing mode `PAY_PER_REQUEST`.
3. Bedrock:
   - one supported model id or inference-profile id from `docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md`,
   - Palmyra X4 direct model id `writer.palmyra-x4-v1:0`,
   - preferred US geo inference id `us.writer.palmyra-x4-v1:0` when available.

## External AWS Source Constraints

The lane depends on these current AWS-documented facts:

1. AWS Palmyra X4 model card:
   - source: `https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-writer-palmyra-x4.html`,
   - lists the Bedrock Runtime endpoint,
   - lists model id `writer.palmyra-x4-v1:0`,
   - lists US geo inference id `us.writer.palmyra-x4-v1:0`,
   - lists `Invoke` and `Converse` as supported APIs.
2. AWS Palmyra X4 parameters:
   - source: `https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-palmyra-x4.html`,
   - records the Writer Palmyra X4 native request and response shape for Bedrock Runtime invocation.
3. AWS Bedrock Converse API:
   - source: `https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference-call.html`,
   - states that `Converse` requires permission for `bedrock:InvokeModel`.
4. Orket local contract:
   - source: `docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md`,
   - admits Writer Palmyra X4 direct and US geo inference ids through the patched `Converse` runtime path.

## Required AWS Call And Permission Envelope

Setup call set, when this lane creates resources:
1. `s3:CreateBucket`
2. `s3:PutPublicAccessBlock`
3. `s3:PutObject`
4. `dynamodb:CreateTable`
5. `dynamodb:DescribeTable`

Runtime permissions for Orket proof execution:
1. `s3:GetObject` on the exact plan object,
2. `bedrock:InvokeModel` on the selected Bedrock model or inference profile,
3. `dynamodb:PutItem` on the smoke audit table.

Cleanup permissions, when this lane deletes resources:
1. `s3:DeleteObject`
2. `s3:DeleteBucket`
3. `dynamodb:DeleteTable`
4. `dynamodb:DescribeTable`

The implementation must not record AWS credential values.
Credential discovery must remain delegated to the standard AWS provider chain.

## Operator Flow

The manual smoke path starts from the existing setup-packet generator and uses randomized concrete names instead of placeholders:

```powershell
python scripts/proof/prepare_trusted_terraform_live_setup_packet.py `
  --bucket orket-smoke-<unique-suffix> `
  --key proof/terraform-plan.json `
  --region us-east-1 `
  --model-id us.writer.palmyra-x4-v1:0 `
  --table-name TerraformReviewsSmoke_<suffix>
```

Then the operator runs the generated AWS setup commands from `workspace/trusted_terraform_live_setup/aws-cli-setup-commands.ps1`, loads the generated non-secret environment values from `workspace/trusted_terraform_live_setup/live-run-env.ps1.template`, and runs:

```powershell
python scripts/proof/check_trusted_terraform_live_setup_preflight.py
python scripts/proof/run_trusted_terraform_plan_decision_runtime_smoke.py --output benchmarks/results/proof/trusted_terraform_plan_decision_live_runtime.json
python scripts/proof/run_trusted_terraform_plan_decision_publication_gate.py
```

The generated cleanup command file remains required handoff evidence for any live attempt that creates resources.

## Randomization Boundary

Allowed randomness:
1. random S3 bucket suffixes,
2. random DynamoDB table suffixes,
3. random Terraform resource names inside valid plan fixtures,
4. random valid create/update/delete/replace action mixes with recorded expected deterministic verdicts.

Disallowed randomness:
1. malformed Terraform JSON on the positive publication path,
2. random AWS mutations beyond the smoke S3 object and DynamoDB audit write,
3. unrecorded random seeds for fixtures used as proof inputs,
4. hidden runtime randomness in deterministic verdict evaluation.

Malformed Terraform JSON is useful only for negative tests and must stay out of the positive publication-gate path.

## Workstream 1 - Disposable Setup Packet

Goal:
1. make the existing no-spend setup packet usable for randomized disposable smoke attempts.

Required implementation:
1. add a small helper or mode that generates a unique smoke suffix,
2. generate bucket and table names from that suffix with operator override support,
3. select Palmyra X4 by default when requested by the operator,
4. emit setup, env, cleanup, and least-privilege policy artifacts,
5. wrap `scripts/proof/prepare_trusted_terraform_live_setup_packet.py` instead of duplicating setup-packet authority,
6. keep generated artifacts out of public benchmark publication unless explicitly approved.

Acceptance:
1. generated names are deterministic from an explicit seed or clearly recorded as generated inputs,
2. generated names avoid placeholders,
3. generated setup packet reports `provider_calls_executed=[]`,
4. setup packet records planned S3, DynamoDB, and Bedrock calls,
5. generated operator commands match the `Operator Flow` command sequence,
6. credentials are not written to any generated artifact.

## Workstream 2 - Randomized Terraform Plan Fixtures

Goal:
1. provide valid Terraform JSON plan objects for live smoke attempts without relying on static toy data only.

Required implementation:
1. create bounded fixture generation for Terraform JSON plan shape,
2. support at least safe create/update-only and risky delete/replace cases,
3. randomize non-authoritative resource names while preserving deterministic expected verdicts,
4. record the fixture seed and expected deterministic outcome,
5. reject malformed generated fixtures before upload.

Acceptance:
1. generated fixtures pass the deterministic Terraform plan reviewer parser,
2. safe fixtures produce `safe_for_v1_policy`,
3. risky fixtures produce `risky_for_v1_policy`,
4. fixture generation is reproducible from a recorded seed,
5. malformed or unsupported action mixes fail closed before AWS upload.

## Workstream 3 - AWS Setup And Cleanup Orchestration

Goal:
1. create and clean up the minimal disposable AWS smoke resources when explicitly invoked.

Required implementation:
1. create the private S3 bucket or fail closed if the bucket already exists outside the lane's ownership markers,
2. block public access on the bucket,
3. upload the generated or selected Terraform plan object,
4. create the pay-per-request DynamoDB table,
5. wait for the table to exist before proof execution,
6. emit cleanup commands or run cleanup when explicitly invoked,
7. make cleanup idempotent where AWS APIs permit it without hiding failures.

Acceptance:
1. setup records observed path and observed result,
2. setup emits the exact live env values needed by Orket,
3. cleanup records observed path and observed result,
4. failed setup cannot be misread as live proof,
5. resources are named and tagged or otherwise identified as smoke-owned when the API supports it.

## Workstream 4 - Orket Live Proof Attempt

Goal:
1. use the disposable AWS inputs to run the existing provider-backed governed-proof path.

Required implementation:
1. set or emit:
   - `ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI`,
   - `ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID`,
   - `AWS_REGION` or `AWS_DEFAULT_REGION`,
   - optional smoke table and trace env values,
2. run `python scripts/proof/check_trusted_terraform_live_setup_preflight.py`,
3. run `python scripts/proof/run_trusted_terraform_plan_decision_runtime_smoke.py --output benchmarks/results/proof/trusted_terraform_plan_decision_live_runtime.json` only after preflight passes,
4. record whether the live proof succeeded, failed, or hit an environment blocker,
5. preserve evidence without claiming public admission.

Acceptance:
1. preflight passes before provider-backed runtime smoke,
2. runtime smoke reports `observed_result=success` or an explicit failure/blocker,
3. Bedrock, S3, and DynamoDB interactions are visible in the proof output path,
4. cleanup remains available after the proof attempt,
5. no public trust wording is changed by this lane alone.

## Workstream 5 - NorthStar Handoff

Goal:
1. produce the exact handoff needed to reopen the paused NorthStar admission lane if live proof succeeds.

Required implementation:
1. write a concise handoff record naming:
   - S3 proof input ref,
   - Bedrock model id,
   - AWS Region,
   - DynamoDB table,
   - runtime smoke output,
   - cleanup state,
   - publication-gate readiness status,
2. state whether the NorthStar reopen criteria are satisfied or still blocked,
3. leave the NorthStar admission lane paused unless the full Workstream 2 proof envelope is rerun in the same change.

Acceptance:
1. successful smoke creates a clear next action for NorthStar Workstream 2,
2. blocked smoke records exact blocker taxonomy,
3. roadmap does not imply public admission unless the NorthStar gates pass,
4. support-only setup evidence is not relabeled as admission evidence.

## Global Implementation Constraints

1. New rerunnable JSON outputs must use `scripts.common.rerun_diff_ledger.write_payload_with_diff_ledger` or `write_json_with_diff_ledger`.
2. Every proof or setup artifact must record observed path as `primary`, `fallback`, `degraded`, or `blocked`.
3. Every proof or setup artifact must record observed result as `success`, `failure`, `partial success`, or `environment blocker`.
4. New or modified tests must be labeled as `unit`, `contract`, `integration`, or `end-to-end`.
5. Live AWS setup commands must be explicit opt-in.
6. Routine local tests must not require AWS credentials.
7. No generated artifact may contain credential values.

## Proof Classification

Expected proof classifications:
1. structural proof: local contract tests for setup packet, fixture generation, IAM/action reporting, and no-credential persistence,
2. no-spend proof: setup preflight with generated non-secret inputs and zero provider calls,
3. live proof: optional AWS-backed setup plus provider-backed runtime smoke when credentials and operator approval are present,
4. absent proof: public admission, replay determinism, text determinism, and arbitrary Terraform workflow trust.

## Closeout Gate

This lane can close only when:
1. disposable setup packet generation is implemented and tested,
2. randomized valid Terraform plan fixture generation is implemented and tested,
3. setup and cleanup paths are documented and, if live credentials are available, executed with teardown proof,
4. the provider-backed runtime smoke is run or truthfully blocked,
5. the NorthStar handoff states whether the paused admission lane can be reopened,
6. `python scripts/governance/check_docs_project_hygiene.py` passes.

## 2026-04-24 Execution Checkpoint

Observed path:
1. structural setup and fixture generation: `primary`,
2. no-spend preflight: `primary`,
3. explicit AWS setup runner without live opt-in flags: `blocked`,
4. provider-backed runtime smoke: `blocked`,
5. publication gate: `blocked`,
6. NorthStar handoff: `blocked`.

Observed result:
1. setup packet generation: `success`,
2. fixture validation: `success`,
3. no-spend preflight: `success`,
4. AWS setup runner without `--execute-live-aws --acknowledge-cost-and-mutation`: `environment blocker`,
5. AWS cleanup runner without `--execute-live-aws --acknowledge-delete`: `environment blocker`,
6. provider-backed runtime smoke with generated non-secret inputs: `failure`,
7. publication gate: `failure`,
8. NorthStar handoff: `environment blocker`.

Evidence refs:
1. setup packet: `workspace/trusted_terraform_live_setup/northstar-disposable-aws-smoke-packet.json`,
2. fixture check: `workspace/trusted_terraform_live_setup/terraform-plan-fixture-check.json`,
3. no-spend preflight: `workspace/trusted_terraform_live_setup/trusted_terraform_plan_decision_live_setup_preflight.json`,
4. setup result: `workspace/trusted_terraform_live_setup/aws-setup-result.json`,
5. cleanup result: `workspace/trusted_terraform_live_setup/aws-cleanup-result.json`,
6. credential scan: `workspace/trusted_terraform_live_setup/credential-scan.json`,
7. runtime smoke: `benchmarks/results/proof/trusted_terraform_plan_decision_live_runtime.json`,
8. publication gate: `benchmarks/results/proof/trusted_terraform_plan_decision_publication_gate.json`,
9. handoff: `workspace/trusted_terraform_live_setup/northstar-handoff.json`.

Generated live inputs:
1. S3 proof input ref: `s3://orket-smoke-e71c67db0f35/proof/terraform-plan.json`,
2. DynamoDB table: `TerraformReviewsSmoke_e71c67db0f35`,
3. AWS Region: `us-east-1`,
4. Bedrock model or inference profile: `us.writer.palmyra-x4-v1:0`,
5. expected plan hash: `sha256:24a54a87f37e64f145b8debd144c3952ce0fe9db6bc50c44896cd05f69701bdd`.

Runtime-smoke blocker:
1. S3 `GetObject` was attempted against the generated S3 URI.
2. The result was `NoSuchBucket` because the disposable AWS setup was not executed.
3. Bedrock `Converse` and DynamoDB `PutItem` were not attempted.
4. The blocker taxonomy is `missing_object`.

Closeout blocker:
1. Live setup and cleanup are not executed because this lane requires explicit cost/mutation/delete opt-in flags.
2. The NorthStar admission lane remains paused.
3. The publication gate reports `publication_decision=blocked` and `public_trust_slice_action=do_not_widen_public_trust_slice`.
4. This checkpoint is not public admission evidence and does not prove replay determinism, text determinism, or arbitrary Terraform workflow trust.
