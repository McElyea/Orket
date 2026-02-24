# OS Contract Index (Authoritative)

This file is the authoritative list of OS v1 contracts.
Anything not listed here is non-authoritative for OS v1.

## OS Program Version
- OS Contract Set: `os/v1`
- Kernel Contract Version: `kernel_api/v1`
- LSI Contract Version: `lsi/v1`

## Normative Documents

| Domain | Contract | File | Version | Authority |
|---|---|---|---|---|
| Governance | Versioning Policy | `versioning-policy.md` | os/v1 | Normative |
| Governance | Test Policy | `test-policy.md` | os/v1 | Normative |
| Governance | Migration Map | `migration-map-v1.md` | os/v1 | Normative |
| Governance | Sovereign Laws v1.2 | `contracts/sovereign-laws.md` | kernel_api/v1 | Normative for replay/capability parity |
| Governance | v1.2 Locked Decisions | `v1.2/open-decisions.md` | kernel_api/v1 | Normative for v1.2 execution |
| Governance | v1.2 Sovereign Laws | `v1.2/sovereign-laws.md` | kernel_api/v1 | Normative for v1.2 execution |
| Governance | v1.2 Implementation Plan | `v1.2/implementation-plan.md` | os/v1 | Normative execution plan |
| Governance | v1.2 PR Workboard | `v1.2/pr-workboard.md` | os/v1 | Normative execution checklist |
| Governance | Kernel Requirements Exit | `KERNEL_REQUIREMENTS_EXIT.md` | kernel_api/v1 | Normative closure gate |
| Governance | Capability + Replay Requirements Exit | `CAPABILITY_REPLAY_REQUIREMENTS_EXIT.md` | kernel_api/v1 | Normative closure gate |

| Domain | Contract | File | Version | Authority |
|---|---|---|---|---|
| Execution | Run Lifecycle | `Execution/run-lifecycle-contract.md` | kernel_api/v1 | Normative |
| Execution | Replay Contract | `Execution/replay-contract.md` | kernel_api/v1 | Normative |
| Execution | Tombstone Wire Format | `Execution/tombstone-wire-format-v1.md` | kernel_api/v1 | Normative |

| Domain | Contract | File | Version | Authority |
|---|---|---|---|---|
| State | Persistence/Snapshot | `State/persistence-snapshot-contract.md` | lsi/v1 | Normative |
| State | Integrity/Linking | `State/integrity-linking-contract.md` | lsi/v1 | Normative |
| State | Digest Spec | `State/digest-spec-v1.md` | lsi/v1 | Normative |

| Domain | Contract | File | Version | Authority |
|---|---|---|---|---|
| Security | Capability/Permission | `Security/capability-permission-contract.md` | kernel_api/v1 | Normative |

## Normative Schemas (JSON Schema)

| Schema | File | Version | Notes |
|---|---|---|---|
| Kernel API Surface | `contracts/kernel-api-v1.schema.json` | kernel_api/v1 | Shape of requests/responses |
| KernelIssue | `contracts/kernel-issue.schema.json` | kernel_api/v1 | RFC6901 required |
| TurnResult | `contracts/turn-result.schema.json` | kernel_api/v1 | Deterministic issue ordering required |
| ReplayReport | `contracts/replay-report.schema.json` | kernel_api/v1 | Deterministic parity results |
| CapabilityDecision | `contracts/capability-decision.schema.json` | kernel_api/v1 | Auditable deny/allow |
| CapabilityDecisionRecord | `contracts/capability-decision-record.schema.json` | kernel_api/v1 | Coexistence parity decision surface |
| Kernel Capability Policy | `contracts/kernel-capability-policy-v1.schema.json` | kernel_api/v1 | Capability policy artifact shape |
| TombstoneV1 | `contracts/tombstone-v1.schema.json` | kernel_api/v1 | Canonical delete payload shape |
| RunLedgerV1 | `contracts/run-ledger-v1.schema.json` | kernel_api/v1 | Sequential promotion high-water mark |
| Error Codes Registry | `contracts/error-codes-v1.schema.json` | os/v1 | Stable code list |
| Error Codes Instance | `contracts/error-codes-v1.json` | os/v1 | Canonical active code set |
| Stage Order Instance | `contracts/stage-order-v1.json` | kernel_api/v1 | Authoritative stage ordering spine |

## Compatibility rule
Any change to a Normative Schema MUST follow `versioning-policy.md` and MUST pass `test-policy.md` gates.
