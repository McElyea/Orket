# Outward Run Claim Tiers v1

Last updated: 2026-05-02
Status: Active durable contract for outward-run proof posture assignment
Owner: Orket Core

## Purpose

Define the lane-local outward proof posture ladder enforced by the outward package verifier and campaign reporter.

## Tiers

| Tier | Minimum evidence | Non-claim |
|---|---|---|
| `outward_lab_only` | one accepted `outward_run_witness_package.v1` verifier report | no repeatability, replay determinism, or public trust |
| `outward_verifier_stable` | two or more accepted verifier reports for the same compare scope with matching invariant signatures and an `outward_run_campaign_report.v1` | no model text or connector-result identity |
| `outward_externally_checkable` | verifier-stable evidence plus clean-environment offline verification, passing corruption suite, and linked assurance case | no public trust-boundary widening |
| `outward_public_trust` | externally-checkable evidence plus same-change update to `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md` admitting the scope | no broader runtime proof |

## Enforcement

The verifier computes the strongest evidence-supported ceiling and rejects requests above that ceiling with `claim_tier_not_supported`.

A single accepted approved, denial, or policy-rejection package can assign only `outward_lab_only`.
