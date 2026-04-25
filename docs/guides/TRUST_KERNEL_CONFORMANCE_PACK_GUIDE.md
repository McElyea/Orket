# Trust Kernel Conformance Pack Guide

Last updated: 2026-04-23
Status: Active evaluator guide

Use this guide to run the portable conformance pack for the current public trust slice.

Canonical command:

```powershell
$env:ORKET_DISABLE_SANDBOX='1'
python scripts/proof/run_trust_conformance_pack.py
```

The command is scoped to `trusted_repo_config_change_v1`.
It does not admit a new compare scope, does not use AWS or remote providers, and does not prove replay determinism or text determinism.

Artifact roles:

1. authority-bearing input evidence: witness bundle, campaign report, validator report, and source authority artifacts referenced by the governed change packet,
2. claim-bearing verifier output: offline verifier report and packet verifier report,
3. claim-supporting derived evidence: finite trust-kernel model report and conformance summary,
4. support-only material: wrapper summaries, generated diagnostics, copied fixtures, and evaluator convenience output,
5. generated corruption: negative cases derived from a positive fixture with the source fixture and mutation recorded.

The conformance summary is not authority by itself.
It points to the evidence and verifier outputs that carry authority.

Supplied-fixture verification:

```powershell
$env:ORKET_DISABLE_SANDBOX='1'
python scripts/proof/run_trust_conformance_pack.py --verify-fixture --packet <path-to-governed-change-packet.json>
```

Supplied-fixture mode is read-only over authority-bearing input artifacts.
It writes only support output paths requested by the evaluator and must not regenerate a clean packet silently.
