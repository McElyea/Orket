# Portable Trust Conformance Pack v1

Last updated: 2026-04-23
Status: Active durable contract
Owner: Orket Core

## Purpose

Define the portable conformance pack required by the Trust Kernel and Portable Conformance lane.

The pack exists to let a skeptical evaluator verify admitted trust evidence without relying on Orket runtime narration, logs, or wrapper summaries as proof authority.

## Scope

Adopted lane scope:
1. active implementation lane: Trust Kernel and Portable Conformance,
2. adopted workstream: portable conformance and verifier pack,
3. initial admitted compare scope: existing `trusted_repo_config_change_v1`,
4. deferred preferred future compare scope: `trusted_repo_manifest_change_v1`.

This contract depends on:
1. `docs/specs/FINITE_TRUST_KERNEL_MODEL_V1.md`,
2. `docs/specs/TRUSTED_RUN_WITNESS_V1.md`,
3. `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`,
4. `docs/specs/GOVERNED_CHANGE_PACKET_STANDALONE_VERIFIER_V1.md`,
5. `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`.

## Non-Goals

This contract does not:
1. admit a new workflow scope by itself,
2. replace the underlying witness, validator, campaign, offline-verifier, or packet-verifier authority,
3. require AWS credentials, remote provider quota, network services, or sandbox resource creation,
4. claim replay determinism or text determinism.

## Artifact Role Rules

PTCP-001. The pack must classify artifacts as:
1. authority-bearing input evidence,
2. claim-bearing verifier output,
3. claim-supporting derived evidence,
4. support-only material,
5. generated corruption.

PTCP-002. The packet remains an operator entry artifact.

PTCP-003. The witness bundle and campaign report where applicable remain authority-bearing proof evidence.

PTCP-004. The offline verifier report and packet verifier report remain claim-bearing verifier outputs over admitted authority-bearing evidence.

PTCP-005. Claim-bearing verifier outputs must not replace the evidence families they verify.

## Conformance Command

PTCP-010. The implementation must provide one canonical command for the full conformance check.

PTCP-011. The command may orchestrate existing verifier commands, but it must not hide:
1. individual verifier substeps,
2. input artifact paths,
3. output artifact paths,
4. downgrade reasons,
5. negative-case reason codes.

PTCP-012. The command must expose the verifier commands or substeps it ran in the conformance summary.

## Supplied-Fixture Verification

PTCP-020. Supplied-fixture verification mode must be read-only over authority-bearing input artifacts.

PTCP-021. Supplied-fixture verification mode must fail closed when required fixture files are missing, malformed, unreadable, contradictory, or outside the admitted compare scope.

PTCP-022. Supplied-fixture verification mode must not silently regenerate a clean packet or clean authority artifact.

PTCP-023. Any regenerated artifact must be emitted to a separate output path and marked support-only unless the evaluator explicitly invokes a generation command.

## Positive And Negative Cases

PTCP-030. The pack must include a positive evidence fixture for each adopted compare scope.

PTCP-031. Each positive fixture must include or link:
1. governed change packet,
2. witness bundle,
3. verifier report,
4. offline claim report,
5. finite model or invariant report,
6. required validator report when the scope uses a validator.

PTCP-032. The pack must include negative fixtures or generated corruptions for:
1. missing final truth,
2. missing approval or operator decision,
3. missing effect evidence,
4. validator failure,
5. authority digest drift,
6. compare-scope drift,
7. projection-only evidence masquerading as authority,
8. unsupported claim request.

PTCP-033. Generated corruptions must preserve a reference to the original positive fixture and identify the exact corruption applied.

## Conformance Summary

PTCP-040. The pack must emit a conformance summary.

PTCP-041. The conformance summary must include:
1. schema version,
2. adopted compare scopes,
3. observed path,
4. observed result,
5. selected claim tier,
6. allowed claims,
7. forbidden claims,
8. positive case results,
9. negative case results,
10. stable signature digests,
11. artifact refs,
12. verifier substeps.

PTCP-042. The conformance summary is claim-supporting derived evidence only when produced by an admitted verifier path over admitted evidence.

PTCP-043. The conformance summary must not become a hidden source of truth above the underlying verifier outputs and evidence families.

PTCP-044. The conformance summary must use `scripts.common.rerun_diff_ledger.write_payload_with_diff_ledger` or `write_json_with_diff_ledger`.

## Proof Classification

PTCP-050. The pack must distinguish:
1. live proof,
2. fixture proof,
3. structural proof,
4. absent proof.

PTCP-051. Fixture-only proof must not be presented as live proof.

PTCP-052. Proof artifacts must record observed path as `primary`, `fallback`, `degraded`, or `blocked`.

PTCP-053. Proof artifacts must record observed result as `success`, `failure`, `partial success`, or `environment blocker`.

## Evaluator Guide

PTCP-060. The pack must include a short evaluator guide.

PTCP-061. The guide must identify:
1. authority-bearing input evidence,
2. claim-bearing verifier outputs,
3. claim-supporting derived evidence,
4. support-only material,
5. generated corruptions.

PTCP-062. The guide must not overstate the proof tier or compare scope.

## Acceptance

PTCP-070. The pack is acceptable only when:
1. one command runs the conformance pack,
2. all positive cases pass,
3. all negative cases fail closed with expected reason codes,
4. unsupported higher claims are downgraded or blocked explicitly,
5. output artifacts are stable and rerunnable,
6. supplied-fixture verification is read-only over authority-bearing input artifacts,
7. the wrapper reports its verifier substeps.
