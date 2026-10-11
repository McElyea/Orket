# 0.8.3: preserve extension Ollama input

Date: 2026-10-10

## What changed

[Issue #6](https://github.com/McElyea/Orket/issues/6) is validated and corrected.
The builtin SDK model owner now uses the existing guarded Ollama transport and
requests full-input admission from the shared prompt policy. The resolved host
profile supplies the input/context budget; oversized requests cannot silently
drop a user message. Application error translation preserves the existing API
HTTP 400 `detail: {ok: false, code, message}` envelope. Default and per-request
provider/model selections share the correction.

Core is 0.8.3; SDK remains 0.8.0. Operator requirements and the compatibility
change are in `CHANGELOG.md` and `docs/specs/MODEL_GENERATION_OPTIONS.md`.
Ollama >=0.24.0 and a resolved profile are required; excessive output requests
now refuse instead of silently lowering the request. Other provider contracts
are unchanged.

## What was verified

**Reproduction:** before the fix, real TCP API/SDK integration omitted `num_ctx`
and returned success for oversized input. A live installed 0.8.2 run against
Ollama 0.24.0/Llama 3.2 3B reproduced the defect: a 520,106-character user prompt
returned HTTP 200/`ok: true`, only 21 measured input tokens, and a generic reply
that lost the secret word. The short control correctly returned `PELICAN`.
The defect is established by runtime evidence, not code inspection alone.

**Live final-candidate proof: primary / success, native Windows.** Fresh
Git-visible sources produced core 0.8.3 and SDK 0.8.0 wheels, installed outside
the checkout. Dependency checks, namespace/license inventory, import origins and
installed package-byte comparisons passed. The installed API factory served
actual authenticated TCP requests through the SDK to a separately owned native
Ollama 0.24.0 CPU server with Llama 3.2 3B and a 4096 server default.

An explicit host profile selected 32768 context for the fixed candidate:

| Request | Observed result |
| --- | --- |
| 626 characters | HTTP 200, `PELICAN`, 216 measured input / 4 output tokens. |
| 19,606 characters | HTTP 200, `PELICAN`, **6056 measured input** / 4 output tokens; 119.36 seconds including API dispatch. |
| 88,506 characters | HTTP 400, `E_MODEL_INPUT_BUDGET`, `ok: false`; 0.031 seconds. |
| 520,106 characters | HTTP 400, `E_MODEL_INPUT_BUDGET`, `ok: false`; 0.032 seconds. |

The model retained the first-line secret beyond the server's former default
window. API shutdown completed and closed its SDK provider. The owned Ollama
Windows Job reported complete capture and confirmed cleanup; its port closed
in the same execution. Routine proof set `ORKET_DISABLE_SANDBOX=1`.
These timings describe this execution, not a performance guarantee.

**Tests:** 234 distinct targeted tests passed with zero failures/errors/skips
(44 warnings). This includes 15 new real TCP/API/SDK/controlled-Ollama cases for
default/override selection, complete request bytes, explicit native guards,
oversized and multibyte input, oversized system prompts, missing profiles,
server/model capacity refusals and explicit larger host context. Related SDK,
API lifecycle, transport ownership/TLS, governed-report and prompt-policy
regressions passed. The 35-test options module passed again after import sorting.
Controlled provider responses prove integration contracts, not live inference.

**Structural checks:** dependency direction passed with 4379 edges/1237 files,
zero violations/cycles/effect violations. Authority checks/rendering, docs hygiene,
version/changelog alignment, touched-file Ruff and scoped mypy on the three
changed runtime modules passed. New-test taxonomy classified all 15 as integration.
Authority validation remains structural, with `current_proof_established=false`.
Architecture checklist AC-01 through AC-10 passes within this boundary: policy
and error translation stay in application services; transport ownership and
schemas are reused; no new completion, storage or replay authority is introduced.

Local ignored evidence: `benchmarks/results/releases/0.8.3/extension-ollama.json`
and `package-inputs.json`; final test results: `.tmp/issue6/final-tests.xml` and
`options-tests.xml`. Final installed artifacts and command logs are retained at
`C:/Users/jonmc/AppData/Local/Temp/orket-issue6-ag2frqqp`.
The earlier candidate/receipt remains at `orket-issue6-hegeghi1` under that same
temporary root. It preceded relocation of error translation into application.

- Package input digest:
  `b60d88d9ee7f0eaa12ab72b7ee230806182f887c43c6424cfd8ce171e48a0a99`.
- Core wheel SHA-256:
  `607f68fc51751cb3ab07419dcd6e185c79f4c749aee2b15c4a2bd51a915d5c35`.
- SDK wheel SHA-256:
  `1f732f81f133e2800ba1467576604c5a0a68f3673c8d9ec6a05a02bd6f7a323b`.

## What was not verified

No full-suite/coverage or hosted CI run, Daniel's machine/corpus, WSL/macOS
reproduction, arbitrary model/template correctness, other-provider live matrix,
streaming acceptance or package-registry publication is claimed. The actual
public API factory and route were exercised; this was not a separate repeat of
the `server.py` launcher. Live tests selected Ollama because the issue is specific
to it, not as a fallback from another provider.

## Remaining blockers or drift

No blocker remains for the reported builtin SDK/API Ollama path. Input admission
is a conservative byte estimate, not exact tokenization; operators may need to
reduce input or explicitly enlarge host capacity. Existing repository-wide lint
and optional typing-dependency drift recorded in the 0.8.2 proof was not part of
this scoped fix. Successful generation still does not certify factual accuracy.

## Exact files touched

- [.gitea/workflows/quality.yml](../../../.gitea/workflows/quality.yml)
- [CHANGELOG.md](../../../CHANGELOG.md)
- [CURRENT_AUTHORITY.md](../../../CURRENT_AUTHORITY.md)
- [docs/CONTRIBUTOR.md](../../../docs/CONTRIBUTOR.md)
- [docs/architecture/CONTRACT_DELTA_SDK_OLLAMA_CONTEXT_2026-10-10.md](../../../docs/architecture/CONTRACT_DELTA_SDK_OLLAMA_CONTEXT_2026-10-10.md)
- [docs/architecture/current_authority.json](../../../docs/architecture/current_authority.json)
- [docs/releases/0.8.3/PROOF_REPORT.md](../../../docs/releases/0.8.3/PROOF_REPORT.md)
- [docs/specs/MODEL_GENERATION_OPTIONS.md](../../../docs/specs/MODEL_GENERATION_OPTIONS.md)
- [docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md](../../../docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md)
- [docs/specs/PROVIDER_INFERENCE_CLIENT_OWNERSHIP.md](../../../docs/specs/PROVIDER_INFERENCE_CLIENT_OWNERSHIP.md)
- [orket/application/services/extension_runtime_support.py](../../../orket/application/services/extension_runtime_support.py)
- [orket/application/services/local_prompting_service.py](../../../orket/application/services/local_prompting_service.py)
- [orket/application/services/sdk_llm_provider.py](../../../orket/application/services/sdk_llm_provider.py)
- [pyproject.toml](../../../pyproject.toml)
- [tests/contract/test_generation_request_options.py](../../../tests/contract/test_generation_request_options.py)
- [tests/integration/test_extension_ollama_input_budget.py](../../../tests/integration/test_extension_ollama_input_budget.py)
