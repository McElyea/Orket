# Native Apple Silicon acceptance operator runbook

Last updated: 2026-10-07

This runbook executes `docs/specs/MACOS_LOCAL_RUNTIME_ACCEPTANCE.md`. It does not
grant Mac support. MAC-02's native process-ownership design and native proof are
still unresolved; current unsupported dispatch must fail. Establish signing access
and a reviewable native design before scheduling a rental. The first authorized
Mac work must prove MAC-02 before attempting the acceptance chain below. A machine
alone does not resolve the entitlement or ownership requirements.
The execution queue and checkpoint remain in
`docs/projects/macos-support/MACOS_SUPPORT_IMPLEMENTATION_PLAN.md`.

The current MAC-02 candidate uses Apple's macOS 27 descendant-scoped Endpoint
Security APIs. These remove root/TCC requirements for that client, but require an
Apple-granted Endpoint Security entitlement and authorized signing/provisioning.
Apple documents a headless executable bundled with its profile; a system extension
is not the only packaging option. No helper/backend has yet been adopted or
verified. Native event-loss, signal identity, client-death and cleanup guarantees
remain open. The pending signing-access question must be answered before treating
this candidate as executable preparation. A rental does not provide the grant.
[Descendant client](https://developer.apple.com/documentation/endpointsecurity/es_new_descendants_client(_:_:)),
[signing requirements](https://developer.apple.com/documentation/xcode/signing-a-daemon-with-a-restricted-entitlement).

## Host proposal and authorization boundary

Proposed test host: one Scaleway M4-XL, M4 Pro with 14 CPU/20 GPU cores, 64 GB
unified memory and 2.05 TB SSD. Public pricing rechecked 2026-10-07 lists EUR
0.49/hour before tax: EUR 11.76 for the mandatory 24-hour minimum or EUR 23.52
for 48 hours. These are calculations from the listed hourly price, not an account
quote or an approved budget. Recheck stock, region, OS image, taxes and the console
estimate before ordering. Public catalogue availability does not reserve capacity.
[Official pricing](https://www.scaleway.com/en/pricing/apple-silicon/).

Scaleway's September 2026 changelog lists macOS 27 on its Mac minis. Select and
verify that OS and a matching SDK if the current ES candidate is adopted; a
generic Dev OS label does not establish either. Public availability is not an
account reservation or native API proof.
[Provider OS announcement](https://www.scaleway.com/en/docs/apple-silicon/).

Prefer a single 24-hour allocation with the provider's automatic deletion option,
collecting evidence well before expiry. An extension needs approval. Billing
continues while the host is allocated, including idle time; shutdown does not
end the rental. There is no deletion before the first 24 hours. The host has MDM
restrictions, including no Recovery access or boot-policy changes. A supervision
design requiring those operations or additional entitlements needs a host/scope
review before spending. [Provider FAQ](https://www.scaleway.com/en/docs/apple-silicon/faq/).

Required approval must identify the account/project, spending limit, rental and
deletion window, and permission to transfer the selected private source candidate,
model and acceptance artifacts. An already authorized equivalent Mac can replace
the rental. No account creation, payment, provisioning, source transfer or runner
registration is performed by the acceptance scripts.

Connection requires a permitted account/IAM identity and a registered SSH public
key. From Windows PowerShell, use the username/address shown by the provider:

```powershell
ssh -i "$env:USERPROFILE/.ssh/orket-mac" mac-user@mac-address
```

Keep the private key on Windows; verify the server identity through the authorized
provisioning record. Only SSH needs to be reachable from the operator; inference
binds to Mac loopback. The Mac needs outbound access to the authorized Gitea/source
service, package indexes and selected upstream downloads. If Gitea is private,
establish its authorized network route before renting.
[Connection and deletion instructions](https://www.scaleway.com/en/docs/apple-silicon/quickstart/).

## Prepare the native host

Use a dedicated acceptance account and an approved source checkout containing the
exact candidate changes, including accepted uncommitted changes if applicable.
Retain its Git metadata and input identity. Do not mistake a checkout of the last
published commit for the current dirty Windows candidate. Transfer only reviewed
inputs after authorization; exclude local credentials, `.env`, unrelated runtime
stores and existing Windows environments. The candidate producer captures fresh
Git-visible package inputs on the Mac. Do not edit that checkout during proof.

Install native arm64 Python 3.11, Git, CMake, Xcode command-line build tools and
the Node runtime required by the selected Gitea checkout action. Record actual
tool versions; the provider image's advertised tools are not verification. Run
these commands in a persistent SSH terminal on the Mac:

```bash
set -euo pipefail
sw_vers
uname -m
python3.11 -c 'import platform; print(platform.platform(), platform.python_version()); assert (platform.system(), platform.machine()) == ("Darwin", "arm64")'
git --version
cmake --version
xcode-select -p
xcrun --sdk macosx --show-sdk-version
node --version
```

Rosetta, a Linux container and an x86_64 interpreter are not this target. Retain
the OS build from `sw_vers` with the acceptance receipt; that receipt also records
kernel release, architecture and Python version. No broader OS support range is
established by testing one configuration.

If native supervision cannot be established within the approved rental window,
retain its failure evidence and perform the same teardown below. Do not treat the
prepared acceptance commands as evidence that the current unsupported backend can
run them, extend the rental without approval, or bypass signing/OS protections.

Prepare the pinned provider outside the Orket checkout, using unused directories:

```bash
git clone --branch b10809 --depth 1 https://github.com/ggml-org/llama.cpp "$HOME/llama-b10809"
cmake -S "$HOME/llama-b10809" -B "$HOME/llama-b10809/build" -DGGML_METAL=ON -DCMAKE_BUILD_TYPE=Release
cmake --build "$HOME/llama-b10809/build" --config Release --target llama-server -j 8
git -C "$HOME/llama-b10809" rev-parse HEAD
"$HOME/llama-b10809/build/bin/llama-server" --version
```

Keep the build output, revision and CMake cache. The
[pinned upstream build instructions](https://github.com/ggml-org/llama.cpp/blob/b10809/docs/build.md)
describe Metal; a successful build is not actual inference evidence.

After approved transfer/download, place the prepared model at an absolute path
whose filename is `orcarouter_Qwen3.8-27B-Uncensored-Q4_K_L.gguf`. The existing
Windows candidate used 18,716,154,112 bytes with SHA256
`431c4818df8a3ce941e2fe35bc37688ea9c30052339eae8f41a4c25cdd9a6fa7`.
Check the selected file with `shasum -a 256`. A different model candidate requires
an explicit recorded identity and the existing provider/prompt admission rules;
do not silently substitute a smaller model or a different provider. The runner
uses the canonical model alias and the installed candidate's Qwen3.8 template.
64 GB is the proposed test capacity, not a promise of model fit.

## Execute the acceptance commands

From the approved Orket checkout, create the contributor harness. It owns the
evidence producer only; all accepted product commands use separate built wheels
in the producer's fresh external environment.

```bash
set -euo pipefail
export ORKET_DISABLE_SANDBOX=1
export PYTHONUTF8=1
python3.11 -m venv .tmp/macos-harness
source .tmp/macos-harness/bin/activate
python -m pip install --upgrade pip
python -m pip install -e "./orket_extension_sdk[testing]" -e ".[dev]"
python scripts/ci/verify_candidate_install.py --require-macos-arm64
python scripts/ci/verify_installed_process_acceptance.py
python scripts/ci/verify_macos_acceptance.py \
  --llama-server "$HOME/llama-b10809/build/bin/llama-server" \
  --model-file "$HOME/models/orcarouter_Qwen3.8-27B-Uncensored-Q4_K_L.gguf"
```

The three commands must succeed in order. The first builds matched core/SDK
wheels and proves fresh installed entrypoints. The second adds that core wheel's
declared dev extra and runs every mandatory native process/uncertainty item against
installed bytes. The final command verifies both retained components and the
unchanged installed dependency inventory, repeats approval/denial and missing
provider controls, supplies answers to the actual setup wizard, starts its own
bounded llama.cpp server and runs the prepared governed-agent workflow. It then
reopens state from fresh processes in a project path containing spaces and Unicode.
Public operator commands are explained in `MACOS_LOCAL_INSTALL.md`.

The server uses loopback, the recorded model/template and a 900-second command
budget. The producer owns cancellation, checks settled capture/descendant cleanup,
and independently confirms the port is closed. Metal acceptance requires named
Metal device/model-buffer allocation, positive GPU layer offload and successful
actual workflow calls against that same owned server. CPU success or device
detection alone cannot pass. Unknown log vocabulary fails; investigate against
the pinned upstream sources instead of relaxing the requirement.

Review `.tmp/macos-support/native-acceptance.json`: all MA-01 through MA-09 must
have `status: PASS`, the overall status must be `PASS`, and
`macos_acceptance_complete` must be true. Source drift, command failure, skipped
process items, missing evidence or uncertain teardown prevent acceptance. Reports
retain individual case status and limits; a partial result is not completion.

For MA-09, inspect the held-loopback missing-provider observation: it must report
the selected endpoint's connection failure, closed provider resources and a
successful settled native diagnostic command. A configuration error (including
a timeout shorter than the provider's connect timeout) is not missing-provider
proof. The producer and both receipt consumers enforce this distinction. Regenerate
earlier candidate receipts that lack it before using the acceptance chain.

For Windows harness development only, run the packaging command without
`--require-macos-arm64` and add `--windows-control` to both later commands, using
the actual local executable/model paths. The combined result may be
`CONTROL_PASS` with MA-05 blocked, `observed_result: partial success` and
`macos_acceptance_complete: false`. That is never a supported-Mac claim.

## Gitea runner configuration

Use a runner binary compatible with the authorized Gitea instance; record both
versions. Download its native macOS arm64 release from the official project and
verify its published checksum. In an account-owned directory outside the checkout:

```bash
runner generate-config > config.yaml
runner register --config config.yaml
runner daemon --config config.yaml
```

Set `runner.capacity: 1` and `runner.labels: ["orket-macos-arm64:host"]` in the
generated configuration before registration. Supply the instance URL and a
repository-scoped registration token at the interactive prompt; keep the generated
registration file private. Confirm the effective label and native host execution
in the Gitea UI. Registration/label precedence is version-dependent; use the
installed version's [runner documentation](https://docs.gitea.com/runner/1/) and
[label documentation](https://docs.gitea.com/runner/labels/).

The manual `.gitea/workflows/macos-candidate-install.yml` workflow accepts absolute
`llama_server` and `model_file` inputs and executes the same three producers. It
does not provision a host, and a label or parsed workflow is not execution proof.
Gitea dispatch tests a published revision; this milestone does not authorize
committing/pushing the current changes. Until publication is separately authorized,
use the manual commands on the reviewed candidate. Preserve the existing Quality
workflow and its required gates; this acceptance job does not replace them.

## Retain evidence and tear down

Before disposing of the host, collect all four canonical reports under
`.tmp/macos-support/`: `package-inputs.json`, `package-install.json`,
`process-acceptance.json` and `native-acceptance.json`. Also copy every external
`area` referenced by the three receipts, including failed attempts. These contain
wheels, installed environments, copied native tests, JUnit, command/server logs,
project files, retained SQLite state and terminal `receipt.json` snapshots.
Keep the approved source snapshot, provider build records and host/tool versions.
The reports contain hashes and original absolute paths; do not rewrite those paths
after retrieval. Record their mapping to the local archive instead.

Use Windows `scp -r mac-user@mac-address:/exact/evidence/path <local-directory>`
for each reviewed evidence directory. Compare downloaded files with their recorded
hashes and confirm all referenced artifacts were included. The model hash is
retained; an existing verified local copy can supply those model bytes. Do not
include runner credentials or SSH keys in the archive.

An interrupted SSH observation is not a stopped proof. Reconnect and inspect the
same live process/job and receipt before launching a replacement. If teardown is
uncertain, retain failure evidence and inspect the recorded process identities;
do not indiscriminately kill unrelated services or erase state to make a rerun pass.

After retrieval, stop the runner, remove its registration in Gitea, and revoke
temporary credentials. At or after the minimum lease, delete the Mac through the
provider console (or confirm the approved automatic deletion). Confirm the resource
is actually deleted and billing allocation ended; shutdown is insufficient. The
provider documents roughly 30 minutes for deletion. Keep the deletion confirmation
and final cost alongside the local evidence before declaring remote teardown done.

Only after all native cases and required repository gates pass may MAC-08 perform
the contributor closeout. Failed or inaccessible native execution remains an open
milestone with its exact next action recorded in the canonical plan.
