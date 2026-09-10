# Governed-agent minor release contract delta

## Summary

- Owner: Orket Core
- Date: 2026-09-10
- Affected contracts: governed-agent v1, SDK package ownership/compatibility,
  core release contract, source-wrapper compatibility window.
- User acceptance: the user accepted the proof and operator experience, selected
  `C:/Source/OrketExtensions/GoverenedAgentLoop`, and authorized all release work
  with a minor bump for core, SDK and extension on 2026-09-10.

## Delta

The development core 0.5.10 / SDK 0.5.0a1 / external 0.1.0 candidate becomes
core 0.6.0 / SDK 0.6.0 / external 0.2.0. The standalone SDK is the sole owner
of its namespace. Core and the reference extension pin SDK 0.6.0; this SDK's
nominal core 0.6–0.8 window is explicitly narrowed to the verified core 0.6.0.

The user-selected external directory is the release source and local artifact
destination. The old `C:/Source/Orket-Extensions/GovernedLocalAgent` directory
is retained as a historical development copy, without release authority.
The source distribution is operator-intake authority. Local distribution does
not imply PyPI publication or a hosted external repository.

The existing `python main.py` wrapper and hidden `--rock` alias remain supported
but deprecated through 0.6.x. Their removal requires an explicit 0.7.0 delta
and remains tracked in the architectural-truth plan. No new compatibility shim
is added. This extends the previous 0.5.x window rather than silently removing
an operator surface during the agent release.

## Migration plan

1. Supply both core 0.6.0 and SDK 0.6.0 wheels to the core upgrade, then
   force-reinstall the SDK wheel with `--no-deps` to restore files removed by
   a historical bundling core's uninstall.
2. Run `pip check`, verify sole SDK namespace ownership, and strictly validate
   the extracted external 0.2.0 source distribution.
3. Use `orket runtime --card` for new runtime callers. Import API composition
   through `orket.runtime.create_api_app`, retaining the returned app; the
   historical module-default API owner is removed by the included B2 change.
4. Apply the core minor-release checklist and installed artifact acceptance.

## Rollback plan

On release regression, retain durable run/effect records and the release evidence.
Reinstall the prior matched artifacts in a fresh environment; do not overlay
an old bundling core into an environment owning the standalone SDK. Existing
uncertain effects require observation and host reconciliation before retry.
An old host must not resume a new governed-agent run it cannot admit.

## Versioning decision

Minor bumps: core 0.6.0, SDK 0.6.0, external 0.2.0, effective 2026-09-10.
Compatibility is breaking for all audiences; migration is required as above.
The completed project is the governed continuous-agent lane. Detailed proof and
release artifact identities live in `docs/releases/0.6.0/PROOF_REPORT.md`.
