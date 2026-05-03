# Outward Run Assurance Case Schema v1

Last updated: 2026-05-02
Status: Active durable contract for outward-run assurance case validation
Owner: Orket Core

## Purpose

Define the machine-checkable claim row shape for the outward-run assurance case index.

## Claim Row Fields

Each row must include:

1. claim id,
2. compare scope,
3. operator surface,
4. allowed posture,
5. invariant ids,
6. authority evidence refs,
7. derived or support evidence refs,
8. verifier command,
9. blocker status.

## Validation Rules

1. `Invariant IDs` must name at least one `ORP-INV-*`.
2. `Authority Evidence` must be present and must not classify support-only material as authority.
3. Single-package verifier commands must consume `--package`.
4. Campaign rows may consume accepted verifier reports through `run_outward_run_witness_campaign.py`.
5. Bundle-only verifier commands are forbidden for proof claims.
6. Denial rows may name `outward_run_write_file_denied_v1` only when the package command includes `--scope outward_run_write_file_denied_v1` and authority evidence names full ledger bytes rather than committed artifact bytes.
7. Policy-rejection rows may name `outward_run_write_file_policy_rejected_v1` only when the package command includes `--scope outward_run_write_file_policy_rejected_v1`, authority evidence names full ledger bytes and `proposal_ref` policy-rejection authority, and committed artifact bytes are absent.
8. Public trust wording is out of scope for this schema.
