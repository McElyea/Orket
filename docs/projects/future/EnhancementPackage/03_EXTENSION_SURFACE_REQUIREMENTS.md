# Extension Surface Requirements

Last updated: 2026-04-02
Status: Draft staged future-lane requirements
Authority status: Staging only. Not current roadmap authority. Not current execution authority until explicitly adopted.
Owner: Orket Core
Lane family: Extension packaging and operator intake

## Purpose

Define one bounded next-step extension-surface delta beyond the already-shipped validate, build, verify, and intake baseline.

This lane exists to harden extension intake into a clearer operator and author surface without pretending the current repo lacks a real extension package story.

## Current shipped baseline

Current authority already ships a bounded extension package surface.
That baseline includes a canonical validation path, bounded manifest support, canonical maintainer build and release verification paths, and operator intake from the published artifact.
This doc does not claim that extension validation and publish posture are unshipped.

## Future delta proposed by this doc

This doc proposes extension-surface hardening beyond the shipped baseline.
Candidate deltas include:
1. explicit install, update, and disable semantics,
2. stronger operator audit and inspection posture,
3. clearer capability and permission declarations,
4. stronger compatibility-class communication,
5. failure-mode hardening for intake and lifecycle operations.

## What this doc does not reopen

This doc does not reopen:
1. a public marketplace plan,
2. a cloud platform plan,
3. hosted extension SaaS,
4. extension autonomy that bypasses host policy,
5. broad catalog or monetization work.

## Usage boundary

This doc should be read as a bounded host-extension requirements candidate.

It should not be read as:
1. a public marketplace plan,
2. a cloud platform plan,
3. permission to weaken host authority in favor of extension autonomy,
4. a claim that the current package, publish, and validation story is absent.

## In scope

1. one bounded delta over the already-shipped extension baseline,
2. package install, update, disable, and intake contract,
3. validation CLI and validation posture hardening,
4. manifest validation,
5. capability and permission declarations,
6. versioning and compatibility rules,
7. operator-facing install and audit story,
8. failure-mode inspection for extension intake and lifecycle operations.

## Out of scope

1. public marketplace or app-store work,
2. monetization or distribution platform work,
3. hosted extension SaaS,
4. extension autonomy that bypasses host policy,
5. broad product catalog work.

## Core requirements

### ES-01. Shipped extension baseline remains the baseline
Any adoption of this doc must start from the existing validate, build, verify, and intake baseline and must not describe the lane as though the extension surface does not already exist.

### ES-02. One canonical extension intake and lifecycle path
The host must expose one canonical operator path for supported extension intake and any newly admitted lifecycle actions such as install, update, or disable.

### ES-03. Validation before execution consideration
Supported extension intake must validate before execution consideration.
Validation success is installability evidence only and must not by itself grant runtime authority.

### ES-04. Manifest family is explicit
The admitted manifest family or families must be explicit and fail closed when unsupported.

### ES-05. Capability declarations are explicit
Extensions must declare the capabilities they request.
The host must not infer privileged capability intent from code shape alone.

### ES-06. Permission declarations are explicit
Extensions must declare permission-relevant resource or effect intents in a bounded schema.

### ES-07. Compatibility rules are explicit
The host must define bounded compatibility rules across:
1. package version,
2. manifest version,
3. host version or contract family where relevant.

### ES-08. Lifecycle actions are operator-auditable
Validation, intake, install, update, disable, and failure outcomes must be inspectable and attributable.

### ES-09. Failure modes are governed
Unsupported manifests, invalid declarations, compatibility failures, and intake-time contract violations must fail closed with stable inspectable error posture.

### ES-10. Host remains the authority center
Extensions remain admitted packages under host policy, not autonomous runtime authorities.

### ES-11. Repo-internal knowledge is not required
A supported extension author must be able to use the supported path without needing informal repo-internal operational knowledge.

## Acceptance boundary

This lane is acceptable only when:
1. one bounded extension delta over the shipped baseline is named,
2. install, validate, publish or intake, and any admitted lifecycle actions have one canonical operator path,
3. manifest, capability, and permission declarations are explicit,
4. compatibility rules are bounded,
5. failure modes are governed and inspectable,
6. supported extension authors do not need repo-internal knowledge to use the admitted path,
7. host policy remains the authority center.

## Proof requirements

Structural proof:
1. no hidden extension admission path bypasses validation,
2. no implicit privileged capability grant exists,
3. no unsupported manifest family succeeds silently,
4. no extension-intake path confuses validation with execution authority,
5. no adoption text understates the already-shipped baseline.

Integration proof:
1. a supported package validates and becomes admissible for execution consideration,
2. an unsupported manifest fails closed,
3. a permissions or capability declaration violation fails closed,
4. operator audit surfaces show intake or lifecycle lineage.

Live proof where real surfaces are involved:
1. the canonical validation path works on a supported package,
2. intake and lifecycle artifacts are inspectable,
3. a compatibility or declaration failure produces truthful operator-visible results.

## Ordering note

This doc is third in the packet because extension-surface hardening should sit on a colder host runtime rather than outrunning it.
