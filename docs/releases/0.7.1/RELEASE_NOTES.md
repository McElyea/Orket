# Orket 0.7.1 - Complete fixture and SDK release cleanup

Complete the outstanding `BT4-FIXTURE-SYNC-RETIRE` release item. `FixtureVerifier`
and `VerificationEngine`, including their deprecated domain exports, are removed.
They previously refused execution; async application verification remains the
sole executor. Location constants, the security exception and unrelated aliases
retain their existing contracts.

`orket sdk --version` now prints the actual SDK version instead of
`OK: None None (None)`. The existing JSON payload is unchanged. Both formats are
verified through the installed console command.

- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`

Replace retired class imports with `FixtureVerificationService` from
`orket.application.services.fixture_verification_service`, supply your explicit
aware UTC clock and workspace, and await `verify(verification)`.

Install the attached matched core and SDK 0.7.1 wheels together:

```text
python -m pip install --upgrade orket-0.7.1-py3-none-any.whl orket_extension_sdk-0.7.1-py3-none-any.whl
python -m pip check
orket ext validate EXTENSION_ROOT --strict --json
```

When upgrading a historical SDK-bundling core, force-reinstall the exact standalone
SDK wheel last with `--force-reinstall --no-deps`. Public SDK behavior is unchanged
from 0.7.0; only the exact Windows 0.7.1 pair is newly admitted. Older matched pairs
retain their own evidence. Core and SDK versions remain independently governed.

Stability remains bounded to Windows. The existing degraded CLI startup warning,
coverage capture/discovery limits, general current-authority proof gap and broader
architectural debt are not closed by this patch. No new inference, Linux/Mac,
hosted CI, Docker or remote-provider acceptance is claimed. The 0.7.x CLI alias
window remains. Published 0.7.0 tags and assets are unchanged. GitHub distribution
assets are published with checksums; this is not a PyPI upload.
