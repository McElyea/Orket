# Orket TechDebt Security Remediation Plan v2 (Phased, Auditable, Deterministic)

Last updated: 2026-03-02
Source: `docs/projects/techdebt/Orket_Brutal_Production_Audit.pdf`

## Summary
Implement the brutal production-grade audit findings as a phased hardening program with strict observability and deterministic behavior guarantees.

Locked additions:
1. Provenance includes runtime security mode snapshot.
2. Every compatibility fallback has explicit expiry markers.
3. Containment rejection behavior is deterministic (stable codes, stable ordering, CI-enforced).

## Project Deliverables (`docs/projects/techdebt`)
1. `README.md`
2. `01-REQUIREMENTS-MAP.md`
3. `02-IMPLEMENTATION-PLAN.md` (this file)

## Locked Decisions
1. Rollout posture is phased: `compat` then `enforce`.
2. Out-of-process extension runtime boundary is a separate follow-on project.
3. Provenance is redacted-by-default.
4. No silent fallback is allowed.
5. Enforcement flip requires policy drift guard: compatibility warning volume must be zero for one full CI run.
6. Severity model is fixed: `P0` critical, `P1` high, `P2` medium/low.
7. Deterministic rejection behavior is required for containment and artifact safety failures.

## Scope
### In scope
1. Extension install pinning and trust policy controls.
2. Artifact containment, symlink refusal, streaming hash and caps.
3. Capability registry hardening and preflight fail-closed behavior.
4. Provenance redaction and security posture snapshot.
5. API auth hardening and insecure-bypass production lockout.
6. Sandbox command-plane hardening and atomic write/locking improvements.

### Out of scope
1. Delivery of out-of-process extension execution runtime.

## Severity Model (for `01-REQUIREMENTS-MAP.md`)
1. `P0` (Critical)
- Direct RCE, traversal/escape, secret exfiltration, auth bypass, supply-chain integrity break.
- Blocks production rollout.
2. `P1` (High)
- Strong exploit preconditions or high blast radius, but not immediate production block.
3. `P2` (Medium/Low)
- Hardening, correctness, observability, maintainability.

Critical definition lock:
- `critical == P0`.
- Gate `zero_critical_open` means no open `P0` items.

## No Silent Fallback Contract
Any compatibility behavior must emit structured warning events and must be visible in:
1. Runtime logs.
2. Per-run provenance/security metadata.
3. CI summary output.

Silent downgrade paths are prohibited.

Required warning event contract:
- `event_name: security_compat_fallback_used`
- Required fields: `component`, `fallback_code`, `mode`, `reason`, `input_ref`, `timestamp_utc`.

Required provenance metadata:
- `security.compat_fallbacks[]` with matching `fallback_code` and context.
- `security.compat_fallback_count`.

Required CI artifact:
- `benchmarks/results/security_compat_warnings.json`
- `benchmarks/results/security_compat_warnings.md`

## Policy Drift Guard
Enforcement mode cannot be activated unless compatibility warning volume is zero for one full CI run.

Enforcement activation requires all:
1. `P0_open == 0`.
2. Security regression suite green.
3. Compatibility warning volume `== 0` for one full CI run.
4. Rollout checklist signed in docs status section.

## Trust Model Definition
### Allowed host patterns
- Canonical config key: `allowed_hosts`.
- Default allowlist for enforcement: `github.com`, `gitlab.com`, `gitea.local`, `localhost`.

### Allowed protocols
- Enforcement allowlist: `https`, `ssh`.
- `file://` and unqualified local path installs are not allowed in production profile.

### Compatibility mode behavior
- Temporary compatibility allowed with warnings and provenance tags.
- Non-allowlisted host/protocol usage records `security_compat_fallback_used`.
- Dangerous sources can still be denied immediately if `block_in_compat=true`.

### Enforcement mode behavior
- Strict host/protocol allowlist.
- Ref must resolve to immutable commit SHA.
- Commit and manifest digest verification required at load/run.
- Fail closed on mismatch.

### Dev profile behavior
- Local path installs allowed only in dev profile.
- Still requires commit pinning and digest recording.
- Must emit explicit `dev_profile_exception` warning metadata.

## Public Interfaces / Type Changes
1. `orket/extensions/models.py` and catalog rows:
- Add `resolved_commit_sha`, `manifest_digest_sha256`, `source_ref`, `trust_profile`, `installed_at_utc`.
2. Provenance contract (`provenance.json`) adds mode snapshot:
- `security.mode = compat | enforce`
- `security.profile = dev | production`
- `security.policy_version = <digest/hash>`
- `security.compat_fallbacks[]`
- `security.compat_fallback_count`
3. `orket_extension_sdk/capabilities.py`:
- Provider execution deferred to `get()`, no side effects at registration.
4. `orket/interfaces/api.py` and `orket/decision_nodes/api_runtime_strategy_node.py`:
- Compatibility: query auth allowed with warning.
- Enforcement: header-only auth; query auth rejected.
5. Containment error contract:
- Stable error code vocabulary and deterministic ordering in containment validators.
6. Compatibility fallback registry contract:
- Each fallback defines `fallback_code`, `introduced_in`, `expiry_version`, `removal_phase`.

## Compatibility Expiry Mechanism
1. Every compatibility branch must include:
- `expiry_version`
- `removal_phase`
2. Add centralized compatibility registry in code:
- One table for all active fallback branches.
3. Add CI check script:
- `scripts/MidTier/check_compat_fallback_expiry.py`
- Fails if expired fallback remains active.
4. Add policy artifact output:
- `benchmarks/results/security_compat_expiry_check.json`.

## Deterministic Failure Contract for Containment
1. Stable error codes:
- `E_EXT_ID_INVALID`
- `E_ARTIFACT_PATH_ABSOLUTE`
- `E_ARTIFACT_PATH_TRAVERSAL`
- `E_ARTIFACT_PATH_ESCAPE`
- `E_ARTIFACT_SYMLINK_FORBIDDEN`
- `E_ARTIFACT_FILE_SIZE_CAP`
- `E_ARTIFACT_TOTAL_SIZE_CAP`
2. Stable ordering:
- Sort failures by `(path_norm, code, detail_digest)` before emission.
3. Deterministic payload shape:
- Canonical JSON serialization rules for error lists.
4. CI enforcement:
- Deterministic ordering assertions run in replay/security regression lane.

## Implementation Phases
### Phase 0: Requirements map and policy baseline
1. Build `01-REQUIREMENTS-MAP.md` with audit finding IDs, severity, owner, target module, status, evidence.
2. Add severity table and critical (`P0`) definition.
3. Add no-silent-fallback and policy drift guard clauses.
4. Define mode snapshot and compatibility expiry contracts.

### Phase 1: Filesystem containment and artifact integrity
1. Implement semantic containment checks (`resolve()+relative_to()`), replacing prefix checks.
2. Validate and sanitize extension/workload IDs used in filesystem paths.
3. Reject symlinks in artifact validation and manifest generation.
4. Replace `read_bytes()` hashing with streaming hash and hard size caps.
5. Emit deterministic containment failures with stable code ordering.

### Phase 2: Install pinning and trust policy
1. Resolve refs to immutable commit SHA before checkout.
2. Perform detached checkout by SHA.
3. Persist and verify commit SHA and manifest digest at load/run.
4. Implement host/protocol trust policy behavior matrix for compat/enforce/dev modes.
5. Add explicit compatibility fallback warnings when compat exceptions are used.

### Phase 3: Capability hardening and provenance redaction
1. Remove arbitrary config provider injection from default path.
2. Enforce required capability preflight with strict behavior in enforcement mode.
3. Switch provenance to redacted-by-default allowlist surface.
4. Add provenance mode snapshot fields (`security.mode`, `security.profile`, `security.policy_version`).
5. Persist fallback warnings into provenance metadata.

### Phase 4: API and sandbox hardening
1. Migrate websocket auth from query+header to header-only in enforcement mode.
2. Block insecure no-key bypass in production profile.
3. Add bounded timeout/cancellation for sandbox compose operations.
4. Enforce safe command argument policy and remove unsafe dynamic surfaces.
5. Add atomic writes and lock discipline for extension catalog/provenance/manifests.

### Phase 5: Enforcement flip and compatibility removal
1. Run full security regression suite.
2. Confirm policy drift guard (`compat warnings == 0` on full CI run).
3. Flip default mode to enforcement.
4. Remove expired compatibility paths according to expiry registry.
5. Finalize docs status and open separate out-of-process runtime follow-on project file.

## Test Cases and Scenarios
1. Path containment suite:
- Reject absolute, traversal, mixed-separator escape inputs.
2. Symlink suite:
- Reject symlinked artifacts that escape root.
3. Artifact-bomb suite:
- File-size and total-size cap failures with deterministic error order.
4. Install pinning suite:
- Ref-move mismatch and tamper mismatch fail closed.
5. Capability suite:
- Unknown capabilities strict-fail in enforcement mode.
- Provider side effects do not execute at registration.
6. Provenance suite:
- Redaction enforced.
- Mode snapshot fields always present and correct.
7. API auth suite:
- Query auth warning in compat.
- Query auth denied in enforce.
- Insecure bypass denied in production profile.
8. Compatibility expiry suite:
- Expired fallback markers fail CI.
9. Deterministic failure suite:
- Repeated runs produce identical ordered containment failure payloads.

## CI / Validation Gates
1. `python scripts/ci/ci_failure_delta.py` before each implementation run.
2. Security regression lane (path/symlink/bomb/pinning/redaction/auth).
3. Compatibility warning artifact generation:
- `benchmarks/results/security_compat_warnings.json`
- `benchmarks/results/security_compat_warnings.md`
4. Compatibility expiry gate:
- `benchmarks/results/security_compat_expiry_check.json`
5. Enforcement flip gate requires all:
- `P0_open == 0`
- security regressions green
- compatibility warnings zero for one full CI run
- compatibility expiry check green

## Acceptance Criteria
1. No open `P0` findings in requirements map.
2. Containment and artifact validation are semantically safe and deterministic.
3. Install/run flow verifies immutable commit and manifest digest.
4. Provenance defaults to redacted payloads and includes security mode snapshot.
5. Compatibility fallbacks are observable, expiring, and CI-enforced.
6. Enforcement mode can be enabled without compatibility warning residue.
7. Out-of-process runtime follow-on is documented as separate project scope.

## Assumptions and Defaults
1. Current in-process extension model remains during this plan; boundary split follows later.
2. Compatibility mode exists only to de-risk migration and is temporary by contract.
3. Production profile is fail-closed for insecure auth and unsafe trust policy paths.
4. Deterministic ordering guarantees are required for replay credibility and CI reproducibility.
