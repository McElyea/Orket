# Governed Repo Change Packet Guide

Last reviewed: 2026-04-19

Use this guide to inspect the first Governed Change Packet without inferring broader proof than the admitted repo-change slice supports.

## Current Truth

- Compare scope: `trusted_repo_config_change_v1`
- Packet schema: `governed_change_packet.v1`
- Standalone verifier schema: `governed_change_packet_standalone_verifier.v1`
- Current truthful claim ceiling: `verdict_deterministic`
- Current proof posture: proof-only and fixture-bounded
- Not yet proven: replay determinism and text determinism

The packet is the primary operator entry artifact. The underlying witness bundle, campaign report, and offline verifier report remain the claim-bearing proof authority.

## Run The Packet Path

Run the packet and verifier commands sequentially when using the default fixture workspace. The adversarial benchmark uses a separate default fixture workspace so it does not rewrite the primary packet refs. If you intentionally override `--workspace-root` or run packet-producing commands in parallel, keep each packet path on a distinct workspace root.

1. Generate the packet and its underlying proof artifacts:

```text
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_governed_repo_change_packet.py
```

Expected result: `observed_result=success`, `claim_ceiling=verdict_deterministic`.

2. Re-run the standalone verifier:

```text
python scripts/proof/verify_governed_change_packet.py --input benchmarks/results/proof/governed_repo_change_packet.json --output benchmarks/results/proof/governed_repo_change_packet_verifier.json
```

Expected result: `observed_result=success`, `packet_verdict=valid`, `claim_tier=verdict_deterministic`.

The verifier report is the packet verdict authority. Read these fields first:

1. `packet_verdict`: `valid`, `invalid`, or `insufficient_evidence`
2. `required_role_diagnostics`: whether every required packet role is present and correctly classified
3. `authority_ref_diagnostics`: whether each authority ref loaded and matched its declared stable authority digest
4. `claim_diagnostics`: whether the requested claim was allowed, downgraded, or rejected by the offline claim ladder
5. `missing_evidence` and `contradictions`: the fail-closed reason lists

3. Inspect the bounded trusted-kernel model:

```text
python scripts/proof/verify_governed_change_packet_trusted_kernel.py --output benchmarks/results/proof/governed_change_packet_trusted_kernel_model.json
```

Expected result: `observed_result=success`.

## Inspect The Authority Artifacts

| Artifact | Path | Role |
|---|---|---|
| governed change packet | `benchmarks/results/proof/governed_repo_change_packet.json` | primary operator entry artifact |
| packet verifier report | `benchmarks/results/proof/governed_repo_change_packet_verifier.json` | packet verdict authority |
| trusted-kernel model report | `benchmarks/results/proof/governed_change_packet_trusted_kernel_model.json` | bounded kernel safety proof |
| approved live proof | `benchmarks/results/proof/trusted_repo_change_live_run.json` | bounded live execution result |
| campaign report | `benchmarks/results/proof/trusted_repo_change_witness_verification.json` | repeated evidence stability |
| offline verifier report | `benchmarks/results/proof/trusted_repo_change_offline_verifier.json` | highest truthful claim ceiling |
| witness bundle | `workspace/trusted_repo_change/runs/<session_id>/trusted_run_witness_bundle.json` | primary bundle authority |
| denial proof | `benchmarks/results/proof/trusted_repo_change_denial.json` | negative proof |
| validator-failure proof | `benchmarks/results/proof/trusted_repo_change_validator_failure.json` | negative proof |

Treat the packet as the entry point for inspection. Treat the witness bundle, campaign report, offline verifier report, and packet verifier report as the claim-bearing proof path.

## Inspect The Benchmark

The current adversarial benchmark candidate is:

```text
benchmarks/staging/General/governed_repo_change_packet_adversarial_benchmark_2026-04-19.json
```

It demonstrates failure classes where the packet plus standalone verifier fail closed while the baseline comparator remains success-shaped or ambiguous.

The comparator is fixed to `workflow + logs + approvals`. It is useful as a baseline because those surfaces can look successful without independently proving authority linkage, validator success, final-truth uniqueness, and claim capping.

## What This Packet Proves

This packet proves that the bounded repo-change slice can:

1. package approval, effect, validator, final-truth, and claim evidence into one inspectable entry artifact
2. cap claims through a standalone packet verifier
3. mechanically reject packet contradictions and missing evidence
4. keep the trusted-kernel claim bounded and explicit
5. expose required-role, authority-ref, and claim-downgrade diagnostics without treating packet projections as proof authority

## What This Packet Does Not Prove

This packet does not prove:

1. arbitrary user workflows are packet-verified
2. the whole runtime is mathematically proven
3. replay determinism
4. text determinism
5. provider-backed governed-proof readiness
