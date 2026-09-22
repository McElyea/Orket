# Provider HTTP catalog inputs and ownership

Last updated: 2026-09-22
Status: Implementation contract; acceptance remains in the architectural-truth plan

OpenAI-compatible and Ollama catalog requests use one immutable environment and
absolute lexical working directory captured before their first await. Synchronous
wrappers capture before crossing the coroutine bridge. Explicit empty environment
means no environment network policy. The same captured inputs govern proxy routes,
certificate locations and optional TLS key logging. Relative paths use the captured
directory; file contents are not snapshotted.

HTTP_PROXY, HTTPS_PROXY and ALL_PROXY select routes through HTTPX's public mount
configuration. Lowercase variables take precedence, including empty lowercase
values, and REQUEST_METHOD suppresses uppercase HTTP_PROXY. NO_PROXY retains HTTPX
host/domain/address/qualified-URL patterns and wildcard bypass. CIDR range syntax
is refused explicitly because HTTPX does not implement subnet matching. No implicit
Windows registry or macOS system proxy lookup remains. Deployments that relied on
those settings must supply environment proxy configuration.

TLS verification remains required. SSL_CERT_FILE takes precedence over SSL_CERT_DIR;
otherwise the declared certifi dependency supplies the default trust bundle, as in
HTTPX. Preserve host certificate verification defaults, including STRICT and
PARTIAL_CHAIN on Python 3.13 and later. The matching host-default test guards this
explicit construction policy against future standard-library drift. Reference:
[Python TLS defaults](https://docs.python.org/3.13/library/ssl.html#ssl.create_default_context).
SSLKEYLOGFILE is honored only from the captured mapping. Its optional file
effect is native owned work. No temporary global environment mutation, private
HTTPX API, unverified TLS or fallback to ambient policy is permitted.

Application ownership retains native certificate/client construction until it
settles, including cancellation and repeated cancellation. Every acquired transport
or client must be closed, even after partial or abandoned construction. Cleanup is
retained through interruption; cleanup failure cannot become successful catalog
completion or clean cancellation. Network operation failures remain visible.

Finite HTTP timeout values retain the existing one-second minimum and HTTPX's
per-phase meaning. Non-finite values fail before native or network admission. This
is not a new total deadline for native filesystem work. Redirects remain disabled;
API-key headers, HTTP errors and model parsing retain their existing contracts.

This contract covers catalog clients, not inference-client composition, actual
model inference, proxy-server correctness, an atomic filesystem snapshot or a full
async audit of TLS library internals. In particular OpenSSL may consult a certificate
directory lazily during handshake. Linux clock repair, full D/E/CAP, release
readiness and lane retirement require their separate acceptance.
