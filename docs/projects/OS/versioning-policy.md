# OS Versioning Policy (Normative)

## Scope
This policy governs versioning for:
- OS contract set (docs/projects/OS)
- Kernel API contracts (kernel_api/v1)
- LSI contracts (lsi/v1)
- JSON schema artifacts in `docs/projects/OS/contracts/`

## Core rule
Breaking changes are forbidden within v1 without an explicit major version bump.

## Version fields
All contract records MUST include explicit version identifiers:
- Kernel DTOs: `contract_version: "kernel_api/v1"`
- LSI records: `lsi_version: "lsi/v1"`
- OS registry artifacts: `os_version: "os/v1"` where applicable

## Allowed change types
### Patch changes (v1.x.y)
Allowed:
- Documentation clarifications that do not change behavior
- Additional examples
- Bugfixes in non-normative text

Not allowed:
- Any change that alters a MUST/SHALL requirement

### Minor changes (v1.x)
Allowed:
- Additive fields to DTOs with safe defaults
- Additive error codes (never rename/remove)
- Additive test scenarios (tightening is allowed)

Not allowed:
- Removing or renaming fields
- Changing meaning of existing fields
- Changing deterministic ordering rules
- Changing canonicalization rules

### Major changes (v2)
Required for:
- Any breaking schema change
- Any behavioral change to promotion atomicity
- Any change to canonicalization or digest rules
- Any change to visibility shadowing (Self > Staging > Committed)

## Deprecation rule
If a field/code is to be retired:
- Mark deprecated in docs for one minor cycle
- Continue accepting it through v1 compatibility
- Remove only in next major
