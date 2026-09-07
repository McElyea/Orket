# Contract Delta: Architectural Truth Command Root

Status: Accepted implementation delta

## Summary

- Change title: One installed runtime root
- Owner: Orket Core
- Date: 2026-07-30
- Affected contracts:
  - `CURRENT_AUTHORITY.md` runtime entrypoints
  - `docs/CONTRIBUTOR.md` canonical commands
  - `docs/RUNBOOK.md` operator commands
  - `README.md` runtime quick start
  - `pyproject.toml` installed `orket` console script
  - `main.py` source-wrapper compatibility status

## Delta

- Previous behavior:
  - the installed `orket` command owns bundle, extension, review, and governed-run
    operations;
  - the documented card runtime is reachable only through checkout-local
    `python main.py`;
  - operators therefore have two unrelated roots, and an installed package does
    not expose the documented default card runtime.
- Accepted behavior:
  - `orket` is the one canonical installed command root;
  - `orket runtime` starts the default card runtime;
  - `orket runtime --card <card_id>` starts one named card;
  - all arguments after `runtime` are parsed by the existing card-runtime parser,
    so no second option implementation exists;
  - `python main.py` and its hidden `--rock` alias remain compatibility-only source
    wrappers through the `0.5.x` release line and are eligible for removal in
    `0.6.0` only after installed-root proof remains green and active operator docs
    contain no canonical source-wrapper instructions;
  - `main.py` delegates to the installed composition root and does not retain a
    second bootstrap or exception-mapping implementation.
- Why this break is required now:
  - installed users need access to the supported runtime without a repository
    checkout;
  - one root removes operator ambiguity while preserving the existing runtime
    implementation and behavioral contracts.

## Migration Plan

1. Compatibility window:
   - `python main.py [runtime arguments]` remains behaviorally supported through
     `0.5.x`;
   - no new source-only alias is introduced;
   - removal is not automatic and requires an explicit `0.6.0` contract delta.
2. Migration steps:
   - make the existing runtime parser accept an explicit argument vector;
   - add a thin `orket runtime` forwarding boundary;
   - update canonical commands and examples to the installed root;
   - retain source-wrapper examples only where explicitly labeled compatibility.
3. Validation gates:
   - `orket runtime --help` from an installed wheel outside the checkout exits `0`;
   - fresh-directory first-run through `orket runtime` persists settings once;
   - handled fatal and invalid-card paths return nonzero through the installed root;
   - direct source-wrapper behavior remains covered during the compatibility window;
   - canonical pytest, changed-file Ruff, and documentation hygiene pass.

Validation result: Passed on 2026-07-30. Evidence is
`docs/projects/architectural-truth/COMMAND_ROOT_PROOF_2026-07-30.md`.

## Rollback Plan

1. Rollback trigger:
   - forwarded arguments differ from `main.py`, installed-root failure status is
     swallowed, or existing non-runtime `orket` commands regress.
2. Rollback steps:
   - remove only the `runtime` subparser and forwarding handler;
   - restore source-wrapper commands as canonical in authority and operator docs;
   - keep the architectural-truth lane active with the failed parity proof.
3. Data/state recovery notes:
   - this change does not migrate durable state or schemas;
   - both roots use the same existing settings and workspace paths.

## Versioning Decision

- Version bump type: Patch when an implementation commit is prepared
- Effective version/date: Implemented 2026-07-30 and released in core `0.5.10`
  on 2026-09-07
- Downstream impact: automation should migrate from `python main.py` to
  `orket runtime`; compatibility remains through `0.5.x`
