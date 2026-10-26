# Platform hardening (milestone 7)

The audit's rate-limit, observability, request-body, readiness and gap-check
accounting issues are addressed on `feat/platform-hardening`.

## Decisions and behavior

- Authentication resolves the hashed API key before the per-key limiter runs.
  Only the stored key UUID enters the limiter; invalid/missing keys remain 401
  and cannot allocate buckets. A `RateLimiter` Protocol permits replacement.
- Each app owns a token bucket with 60 requests of initial burst capacity and
  continuous one-token-per-second refill by default. Limits apply in every
  environment. A rejected call returns the normal error envelope, request ID and
  a rounded-up `Retry-After`. The 10,000-identity bound evicts only inactive,
  fully refilled buckets; saturation rejects new identities until space recovers.
  Configure these with `LABDOCS_RATE_LIMIT_PER_MINUTE` and
  `LABDOCS_RATE_LIMIT_MAX_IDENTITIES`.
- The limiter is process-local. Run one API worker/replica for this deployment;
  multi-worker production needs a shared atomic store such as Redis. Invalid-key
  traffic still reaches authentication; Internet-facing deployments need an edge
  request limit as well. Health/readiness/metrics remain unauthenticated.
- Prometheus records complete request duration, route templates and bounded HTTP
  method labels. UUIDs and random unmatched URLs do not create labels. Rejected
  429/413 and unhandled 500 responses are counted. Scrapes and health probes do
  not count themselves. Each app has its own registry.
- `LABDOCS_MAX_REQUEST_BYTES` defaults to 26 MiB, covering multipart framing as
  well as content; `MAX_UPLOAD_BYTES` remains 25 MiB. Declared lengths are checked
  early and bytes are counted even with absent or false Content-Length. A bounded
  disk spool (1 MiB in memory) rejects oversized input before a handler can act.
  This is a per-request bound; disk space and connection limits remain operational
  responsibilities. Set the proxy body limit consistently during packaging.
- Startup performs an embedding call before readiness succeeds. `/readyz` also
  checks Postgres and the configured Qdrant backend, and reports `embedder: ok`.
  First startup may need to download the embedding model. Browser tests inject a
  deterministic embedder and an explicit high request rate in their isolated
  entrypoint; production has no testing-environment bypass.
- The existing database unique index enforces one active gap job per key, even
  under concurrent submissions. The configurable setting now accepts only 1,
  matching the database rather than promising unsupported higher concurrency.

## Gap-check budget and reported usage

Each provider attempt reserves its serialized UTF-8 request size plus 1,024
framing tokens and the requested maximum output before starting. Concurrent
judgements share one allowance. HTTP retries and judgement-validation retries
must reserve again. Cache hits are free. Queueing judgements check cancellation
again after acquiring a concurrency slot.

Successful responses release unused allowance when positive usage is reported.
Invalid judgements still count their reported usage. Timeouts, transport failures,
invalid provider envelopes and missing/zero usage retain their full reservation;
they cannot reopen the allowance for free retries. Report metadata distinguishes
provider-reported `token_usage` from `token_budget.charged_tokens` and
`unreported_tokens_reserved`. The latter are conservative allowances, not measured
billing. Calls that cannot reserve yield explicit `judge_failed` findings and the
`tokens` cap flag. A provider that reports more than its reservation is recorded
honestly and prevents further calls; the report is never clamped to conceal it.

**Limit:** this is a hard admission limit on the conservative allowance, not a
universal guarantee of provider-billed tokens. UTF-8 byte accounting conservatively
covers ordinary byte/subword text tokenizers, but a remote provider's hidden
reasoning, tokenizer or noncompliance with output limits cannot be controlled by
this API. Such provider overruns are disclosed in metadata. Provider-specific
exact token counting and billing reconciliation remain future work. This
qualification replaces the old unsupported claim of an absolute billed-token cap.

## Verification

Results and CI links are recorded below after the completed checks. Tests cover
continuous refill and rounding, thread and request concurrency, identity eviction,
401/429 isolation, request IDs and 500/413/429 metrics, route-label cardinality,
chunked and misleading-length bodies, exact size boundaries, concurrent token
reservations, cache hits, failed validation accounting, provider retries/timeouts,
missing usage and provider overruns. The full existing backend and browser suites
remain required. These checks do not establish regulatory judgement quality.
