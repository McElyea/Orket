# Governed Agent Loop Slice 7 Packaging Checkpoint

Archived on 2026-09-10 after user acceptance and the governed-agent minor-release
closeout. Current release authority: `docs/releases/0.6.0/PROOF_REPORT.md`.
The checkpoint/version/blocker statements below are historical as of their
recorded dates; the accepted closeout supersedes their open release gates.

Date: 2026-09-07
Status: Packaging and clean-install checkpoint complete; lane remains active
Observed path: `primary`
Observed result: `success`
Proof classification: live clean build, install, import, and validation proof

## Outcome

The current Git-visible worktree was copied into a cache-free source stage so
ignored `build/` and `*.egg-info` state could not influence package discovery.
Core `0.5.10`, SDK `0.5.0a1`, and the external starter `0.1.0` each built a
wheel and source distribution. A fresh virtual environment installed the three
final wheels together with resolved dependencies.

The first cache-free external-starter build exposed a real drift: its source
distribution omitted `extension.yaml` and `test_governed_agent.py`. The
template now has an explicit source manifest and an integration test that
builds a clean copy and inspects the archive. The core build also no longer
uses setuptools' deprecated license-table metadata; the installed distribution
reports the SPDX expression `BUSL-1.1` and retains `LICENSE` explicitly.

## Artifact Evidence

| Artifact | SHA-256 |
| --- | --- |
| Core `0.5.10` wheel | `BB3B5DA87A027AEC6DD2848B9B312AA9FD16CCFBA47933E87510C96005CA2089` |
| Core `0.5.10` source distribution | `C1DFE4E842F345BB7D510339C4F83C3D6CC22F778775B51C931963D2C25BB85E` |
| SDK `0.5.0a1` wheel | `31B33103A63344DFB2C778713AEF1FA4C0730D4FB6AFB64E9A0D05A30387328F` |
| SDK `0.5.0a1` source distribution | `BE8527F927678744F2BBD78BE5AB97E8C2E75392753BF25D5B73F4A17E86D3C1` |
| External starter `0.1.0` wheel | `095F146C48FBDD8A1DDAE2EFB47885BCF4023A3DCBCA1CAC374FAF50625B50ED` |
| External starter `0.1.0` source distribution | `72155ADC4DF52D4D6E21271E95A697D23BCFB293E1DFA491EAF355ABF81720CF` |

The core wheel and source distribution each contain zero
`orket_extension_sdk` entries. The SDK wheel retains the canonical governed
agent schema. The external source distribution contains one root
`extension.yaml` and one `test_governed_agent.py`.

## Verification

1. Cache-free source stage: `3993` existing Git-visible files copied; ignored
   build metadata and caches excluded.
2. Isolated wheel and source-distribution builds for core, SDK, and external
   starter: pass.
3. Fresh three-wheel install with dependency resolution: pass.
4. `python -m pip check`: `No broken requirements found.`
5. Core, SDK, and external imports: all resolved beneath the fresh virtual
   environment's `site-packages`; versions were `0.5.10`, `0.5.0a1`, and
   `0.1.0` respectively.
6. Installed `orket agent --help`: pass; `wake`, `inspect`, `replay`, `cancel`,
   and `submit` were present.
7. Installed SDK strict validation plus import scan against the extracted final
   external source distribution: zero errors, zero warnings, two files scanned.
8. Installed host `orket ext validate <extracted-root> --strict --json`: zero
   errors, zero warnings, two files scanned.
9. `python -m pytest -q tests/integration/test_governed_agent_external_package.py`:
   `1 passed in 0.57s`.
10. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q`: `4540 passed, 56 skipped,
    2 warnings in 484.97s`; the warnings are the existing deprecated
    `orket.domain` import and governed-output low-token warnings.
11. Architectural-truth baseline regeneration: `collection_ok=true`,
    `release_ready=false`; known debt was not promoted to green.

The canonical repository suite and architectural gates are also reconciled in
the Slice 6H proof. This checkpoint does not substitute package success for
runtime or release acceptance.

## Not Verified

1. The final built artifacts were not published, tagged, or hosted. Those are
   separate release actions governed by core and SDK release policy.
2. At this checkpoint, live Ollama inference had not been rerun from these
   installed artifacts. The subsequent installed-runtime checkpoint exposed
   their missing default prompt registry, rebuilt core with its canonical
   registry packaged, and passed five live flows. Its core hashes supersede
   this checkpoint for runtime proof; SDK and starter hashes are unchanged.
   See `SLICE_7_INSTALLED_RUNTIME_CHECKPOINT_2026-09-08.md`.
3. User acceptance and the consolidated Slice 7 release decision are not
   implied by this packaging checkpoint.

## Remaining Blockers or Drift

1. Slice 7 still requires final evidence reconciliation, policy-governed
   version/release actions, and explicit user acceptance before lane closeout.
2. `AT-EX-003` and the architectural-truth baseline's wider release-readiness
   debt remain outside this bounded package checkpoint.
3. Scheduler evaluation-window discovery remains caller-owned by accepted
   contract; it is an intentional boundary, not unimplemented Orket authority.
