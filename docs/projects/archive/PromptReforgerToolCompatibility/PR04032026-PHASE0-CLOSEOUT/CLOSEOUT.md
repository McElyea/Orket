# Prompt Reforger Phase 0 Closeout

Last updated: 2026-04-03
Status: Completed
Owner: Orket Core

Active durable authority:
1. [docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md](docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md)
2. `orket/reforger/service_contracts.py`
3. `orket/reforger/proof_slices.py`
4. `orket/reforger/service.py`
5. `CURRENT_AUTHORITY.md`

Archived lane record:
1. [docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/Phase0ImplementationPlan.md](docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/Phase0ImplementationPlan.md)
2. [docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/PromptReforgerGenericServiceRequirements.md](docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/PromptReforgerGenericServiceRequirements.md)
3. [docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/LocalClawExternalHarnessRequirements.md](docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/LocalClawExternalHarnessRequirements.md)
4. [docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/PromptReforgerLocalClawExternalBoundaryNote.md](docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/PromptReforgerLocalClawExternalBoundaryNote.md)

## Outcome

The Prompt Reforger tool compatibility Phase 0 lane is closed.

Completed in this lane:
1. a generic Prompt Reforger service surface now executes the bounded Phase 0 request/result contract without adding consumer-specific runtime code
2. deterministic service-run and scoreboard artifacts now exist for the frozen LocalClaw-style textmystery proof slice, and qualifying runs freeze an explicit compatibility-bundle section only when thresholds are met
3. the bounded external-consumer proof path now records `verdict_source=service_adopted` for the exercised tuple without merging consumer authority into Orket
4. live proof against a real local runtime remains explicitly blocked and is recorded as such inside the canonical staging artifacts rather than being presented as a false-green live pass
5. roadmap, archive, authority, and staging catalog surfaces were closed in the same change

## Verification

Observed path: `blocked`
Observed result: `environment blocker`

Executed proof:
1. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/reforger/contract/test_prompt_reforger_service_contracts.py tests/reforger/integration/test_prompt_reforger_service.py` (`5 passed`)
2. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/reforger/compiler/test_compile_textmystery_v0.py tests/integration/test_reforger_tools_family.py tests/application/test_reforger_pr1_pack_mode.py tests/application/test_reforger_cli_layer0.py tests/reforger/determinism/test_reforge_repeatable.py` (`18 passed`)
3. inline Phase 0 structural service execution wrote:
   - `benchmarks/staging/General/reforger_service_run_phase0-baseline-run-0001.json`
   - `benchmarks/staging/General/reforger_service_run_phase0-baseline-run-0001_scoreboard.json`
   - `benchmarks/staging/General/reforger_service_run_phase0-adapt-run-0007.json`
   - `benchmarks/staging/General/reforger_service_run_phase0-adapt-run-0007_scoreboard.json`
4. `python scripts/governance/sync_published_index.py --index benchmarks/staging/index.json --readme benchmarks/staging/README.md --write` (pass)
5. `python scripts/governance/sync_published_index.py --index benchmarks/staging/index.json --readme benchmarks/staging/README.md --check` (pass)

Live-proof blocker:
1. No real local-model runtime is configured for the bounded Phase 0 proof slice, so the service artifacts remain `proof_type=structural` and record `observed_path=blocked` / `observed_result=environment blocker` for the live-proof seam.

## Remaining Blockers Or Drift

1. Live proof against a real local runtime remains blocked until a concrete Phase 0-compatible local model runtime is configured for the frozen proof slice.
2. Broader Prompt Reforger expansion beyond the bounded Phase 0 generic service slice must reopen as a new explicit roadmap lane.
