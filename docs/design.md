# Design

Working notes and decision records for `labdocs`.

## Decisions

### Frontend upgrade audit (F0, 2026-10-25)

- [FRONTEND_SEED.md](../FRONTEND_SEED.md) overrides SEED on frontend design,
  dependency and layout choices. [F0 audit and plan](frontend-f0-audit.md)
  records the reuse map, file layout, gates and untracked-baseline Git issue.
- Use hand-written components, CSS Modules and shared tokens with system fonts.
  Settings context plus small async/polling hooks suffice; no query/state library.
  Retain the existing Oxlint installation; adding ESLint is outside the newly
  approved dependency list and would require approval.
- Keys stay in sessionStorage; non-secret preferences use localStorage. Store
  only the last ten Q&A in sessionStorage. Model/document output remains text.
- F0 enables strict in both TypeScript projects. Only F1 introduces the approved
  test/router/icon dependencies. Missing frontend suites are recorded as absent,
  never made green with skip or allow-no-tests flags.
- Deterministic browser runs use the fake provider and an isolated test corpus.
  Its stock default does not provide valid structured outputs. A test-only
  startup harness can script the existing FakeLLM without modifying app code.
  The local Qwen model is reserved for manual checks.
- Browser AbortController cancellation stops waiting locally; only the existing
  gap-job cancel endpoint supplies cooperative server cancellation. Explain the
  distinction in UI copy. Never report a job cancelled before the API does.
- Approved F0 follow-up: label local abort **Stop waiting** and server gap
  cancellation **Cancel run**. Omit unsupported provider/model chips; mention
  unavailable values only in Details. Drop document chunk counts if their
  bounded detail requests make the table slow.
- Playwright starts in F1 with all-route 1280/390/360px screenshots and page
  overflow assertions. Commit only final milestone screenshots. Initial route
  JS has an approximately 110 kB gzip budget, reported per PR. Oxlint permits
  no new warnings; F5 removes the three Documents warnings and makes them fatal.

## Frontend API needs

Recorded during F0 against the current generated contract. These are proposals
for separate backend work, **not backend changes authorized by this upgrade**.
Missing fields must not be invented in frontend interfaces. Render the fallback
until an approved endpoint/type change exists.

| Need / affected milestone | Current contract | Minimal proposed change | Frontend behavior now |
| --- | --- | --- | --- |
| Structured errors and field validation (F1) | Most runtime errors use `{error:{code,message,request_id}}`, but OpenAPI advertises FastAPI's different `HTTPValidationError` for 422 and omits other error responses. Field errors are not returned | Document the existing envelope on response models; optional safe field-name/message details | Parse unknown bodies with guards; validate known field constraints locally; otherwise show form-level error. Never copy request headers/key into details |
| Readiness detail (F1) | `/readyz` response is only a generic string-keyed object in generated types; runtime returns nested status/checks. No embedder-loaded check | Typed readiness response and optional embedding status | Narrow nested values at runtime. Show only supplied checks; say model readiness is unknown. Do not infer model readiness from database success |
| Live limits and backend capabilities (F1/F4/F5) | No endpoint reports enabled backends, upload bytes, SOP chars/clause cap or model configuration. Defaults are 25 MiB, 200,000 SOP chars, 80 clauses; env may change them | Optional typed capabilities/limits response | Validate documented default file limits/types, bound fields using known schema constraints, and handle authoritative 413/422. Do not claim defaults reflect runtime overrides; backend selection failures remain visible |
| Cited chunk text and passage position (F2/F3/F4) | Ask/Agent and gap citations include `document_id`, `chunk_id`, title, page, score and excerpt; no full-chunk lookup or cited-span offsets. Search has full text for its own returned hits | Optional read-scoped chunk lookup with text/span metadata | Show the supplied excerpt labelled as an excerpt. Reuse exact known search-hit text only for the same chunk ID. Enrich agency/year/version with existing document detail; show unavailable if that fails |
| Inline citation placement (F2/F3) | `answer` is an unconstrained string and citations are an array. `[n]` markers are not guaranteed by the API | Optional structured answer segments or documented stable marker-to-citation ordering | Parse only valid in-range markers as React text/chip nodes. Supply a numbered source list when no markers exist; never invent inline placement or render HTML |
| Model/provider in Ask/Agent (F2/F3) | Response schemas have no model/provider. Gap report metadata may contain a model string | Optional model/provider fields in response metadata | Omit optional chips; mention unavailable only inside Details. Do not label it Qwen from local assumptions |
| Agent truncation flag (F3) | `AgentTraceStepResponse` exposes `result_summary` but no `truncated` boolean. Current tools append `; output truncated` to summaries | Optional per-step `truncated: boolean` | Preserve summary as text and label truncation when that explicit marker is present; do not fabricate a response field |
| Progress-time caps (F4) | `GapCheckProgress` has phase and clause/requirement totals/done; `caps_hit` lives in the final report | Optional `caps_hit` on progress | Show report caps after completion and input cap errors immediately. During active polling, do not suggest caps have been checked |
| Gap run metadata / ingestion report schemas (F4/F5) | `GapCheckReport.metadata` and `IngestionJobResponse.report` are `Record<string, unknown>`; there is no generated typed report body | Typed nested metadata and ingestion report models | Narrow observed keys safely, show unavailable when absent and preserve JSON export. Render post-commit sync warning from supplied failure/report text; do not assume success across both stores |
| Document chunks and global search/sort (F5) | List already supports metadata/year filters, limit/offset and total, but no title search/sort parameters or chunk count. Detail returns chunk count | Optional list chunk count and title/sort query parameters | Use existing server pagination/filters. Label text search/sort as applying to the loaded page; fetch/cache detail counts for visible rows with bounded concurrency; drop the column if slow |
| Alternate API base URL (F1) | Vite `/api` proxy works; API has no configured CORS allowance for other origins | Separate deployment-specific CORS configuration if needed | Default `/api`; allow same-origin proxies, explain cross-origin failure and show network errors. Do not change backend CORS or put keys in URLs |
| Cancellation (F1/F3/F4/F5) | Gap jobs have POST cancel and terminal status polling. Ask/Search/Agent have no server cancellation API; ingestion has none | Optional server cancellation only as separate work | Abort local requests, retain honest wording about server work, poll gap cancellation to terminal status and do not offer fictitious ingestion cancellation |

Pagination, regulation filters, gap upload and gap cooperative cancellation are
already supported and need no API change. A 429 from the current limiter may
lack a request ID; show unavailable and use `Retry-After` where provided.

## Decisions (continued)


### Scaffold (milestone 0)

- 2026-10-23 — Python pinned to `>=3.12,<3.13` per SEED.md §5; `uv` provisions 3.12 (the system interpreter is 3.14).
- 2026-10-23 — Trunk `main`; the initial scaffold commit landed on `main`, feature work uses short-lived `feat/<milestone>` branches.
- 2026-10-23 — FastAPI 0.161.1 ships no `fastapi.mypy` plugin; mypy runs without it rather than pinning an older FastAPI.
- 2026-10-23 — Git remote configured after the scaffold: `origin` = `git@github.com:bunbun205/Regulatory-Docs-Copilot.git` over SSH. CI runs on GitHub Actions. (Supersedes the earlier "no remote configured" note.)
- 2026-10-23 — Docker CLI, daemon and Compose are installed and active. Docker group membership was added during milestone 2; existing shells need a new login or `newgrp docker` before they can reach the socket. `docker compose config` is validated in CI.
- 2026-10-23 — `qdrant/qdrant` pinned to `v1.20.0` (latest stable at the time) instead of `latest`. Compose project is named `labdocs` and Postgres credentials are environment-overridable.
- 2026-10-25 — Postgres is pinned to `pgvector/pgvector:0.8.7-pg16` in compose and CI. The floating `pg16` tag was replaced because filtered search depends on `hnsw.iterative_scan`, introduced in pgvector 0.8.0. Startup and the ingest/reindex CLI fail when the database extension is older than 0.8.0.
- 2026-10-23 — Logging fix: the stdlib format is `%(message)s` so structlog output is pure JSON, and the configured level drives both stdlib and structlog filtering (previously the level was hardcoded to INFO and logs had a text prefix).
- 2026-10-23 — CI actions bumped to current published versions (`actions/checkout@v7.0.1`, `actions/setup-python@v7.1.0`, `astral-sh/setup-uv@v10.3.2`) to clear Node 20 deprecation warnings. `setup-uv` has no rolling major tag, so exact versions are pinned.

### Foundation (milestone 1)

- 2026-10-23 — Async SQLAlchemy 2.x with `asyncpg`; Alembic uses the async engine. The engine and session factory are created in the FastAPI lifespan and disposed on shutdown. Installed SQLAlchemy is 2.1.6; SEED's "SQLAlchemy 2.0" is treated as the 2.x major line.
- 2026-10-23 — API keys: `labdocs_` + 32 random bytes (URL-safe), stored only as an unsalted SHA-256 hex digest. Unsalted is appropriate here because keys are high-entropy and lookup is by digest; names are unique.
- 2026-10-23 — A single stored scope (`read` or `write`); `write` implies `read`. `/v1/whoami` reports effective scopes, so a write key returns `["read", "write"]`. This is the simplest reading of SEED's single-scope model that still lets write keys read.
- 2026-10-23 — Error envelope is exactly `{"error": {"code", "message", "request_id"}}`. Validation details are logged, not returned; 500 responses never include exception text.
- 2026-10-23 — Request IDs: a caller-supplied `X-Request-ID` is accepted when it matches `[A-Za-z0-9._-]{1,128}`, otherwise a UUID4 hex is generated. The value is echoed on every response and bound to structlog context for that request.
- 2026-10-23 — `/readyz` checks the database. Milestone 3 adds a Qdrant check when that backend is configured; the lazy embedder is not force-loaded by readiness.
- 2026-10-23 — Only the `api_keys` table is introduced in milestone 1. Documents, chunks and job tables land with the milestones that actually use them rather than being designed speculatively.

### Ingestion + ETL (milestone 2)

- 2026-10-23 — **Postgres-only tests.** `LABDOCS_TEST_DATABASE_URL` defaults to
  `postgresql+asyncpg://labdocs:labdocs@localhost:5432/labdocs_test`, and the test
  fixture refuses any database whose name does not end in `_test`. This is
  stricter than the earlier SQLite fallback on purpose: `Vector(384)`, PostgreSQL
  `ON CONFLICT` upserts and content-hash idempotency are the behavior under test,
  so verifying them on SQLite would prove the wrong thing. Compose creates
  `labdocs_test` through `infra/postgres/01-create-test-db.sql`; CI uses
  `labdocs_test` as its service database. The full suite and the double-ingestion
  check were run locally against compose Postgres before opening the milestone PR.
- 2026-10-23 — **Schema and migration.** `documents` has a unique raw-byte
  `content_sha256`, source metadata, byte size and optional page count. `chunks`
  stores text, approximate token count, optional `page`/`section_heading`, a
  `vector(384)` embedding, and is unique on `(document_id, chunk_index)` with a
  cascading FK. `ingestion_jobs` stores `queued|running|completed|failed`, a JSONB
  report, safe error text and timestamps. Migration `0002` creates the `vector`
  extension and the three tables/indexes. Milestone 3 adds the HNSW cosine index
  in migration `0003` together with search and the vector-store contract.
- 2026-10-23 — **Manifest validation.** Pandas reads the CSV as strings. Missing
  required columns, an unreadable/empty CSV, or a header-only file fail the job.
  Bad rows are rejected with reasons instead of aborting: missing fields,
  duplicate filenames, unsupported extensions, non-`YYYY` or out-of-range years
  (1900–2100), missing files, and filenames that are not bare names. File paths
  are resolved and must stay inside the supplied documents directory, so path
  traversal and symlink escapes are rejected. Extra manifest columns are ignored.
- 2026-10-23 — **Dedupe and idempotency.** Dedupe is by SHA-256 of the raw file
  bytes, not filename. A preflight lookup avoids extracting/embedding known
  content, and the actual insert uses PostgreSQL
  `INSERT ... ON CONFLICT (content_sha256) DO NOTHING RETURNING id` so concurrent
  jobs are safe. A document and all of its chunks are committed in one
  transaction. Re-running the same manifest therefore creates zero documents and
  zero chunks and performs no embedding calls.
- 2026-10-25 — **Document identity and update semantics (condition 4).** A
  document's stable identity is `(source_agency, filename)`, enforced by
  `uq_documents_agency_filename` in migration `0004`. Classification order is:
  an existing global content hash is a **duplicate**; the same identity with a
  different content hash is an **update**; everything else is **new**.
  Metadata-only changes (title, doc_type, year, version) for the same identity
  are reported as duplicates but update the Postgres metadata and the Qdrant
  payloads; they do not re-chunk or re-embed. For a content update, the pipeline
  locks the document row, updates metadata, deletes all old chunks and inserts
  the new chunks in one Postgres transaction. After commit it deletes the
  document's points from Qdrant and inserts the new points. A shorter
  replacement document was tested and leaves no old chunks. If the external
  replacement fails, Postgres keeps the new content and the job fails safely;
  re-ingesting the same new content is a duplicate and repairs Qdrant. A
  duplicate re-ingest also replaces external points rather than merely upserting,
  so stale points for that document are removed. The follow-up section below
  records the final metadata-update semantics and report fields.
- 2026-10-23 — **Recursive chunking.** Splitting proceeds paragraph → sentence →
  word → character, targeting ~500 tokens with ~80 tokens of overlap. PDF pages
  are preserved as `page`; Markdown headings become `section_heading`; plain text
  has neither. Token counts are deliberately approximate: a small regex tokenizer
  avoids downloading/loading the embedding tokenizer during chunking. This is
  labelled in the report and is a known limitation if exact BGE token limits are
  required later.
- 2026-10-23 — **Embedding.** `sentence-transformers` with
  `BAAI/bge-small-en-v1.5`, 384 dimensions, CPU only, batched and L2-normalized
  with NumPy. The model is loaded lazily on the first non-empty embed request.
  Tests inject a deterministic `FakeEmbedder` and never download model weights.
  Torch comes from the PyTorch CPU index and is bounded `<2.7` because that index
  currently stops at `2.6.0+cpu`; the alternative was pulling multi-gigabyte CUDA
  wheels for a CPU-only service.
- 2026-10-23 — **Scope boundary.** SEED §6.3 says embeddings are written to the
  configured vector store(s) and Postgres. Milestone 2 writes documents, chunks
  and pgvector embeddings to Postgres, which is the source of truth. Qdrant
  fan-out, the `VectorStore` Protocol and search belong to milestone 3, which
  SEED orders next; implementing them early would violate the ordered milestones
  and the "contract tests on both backends" acceptance criterion. This is a
  deliberate, recorded deviation from the broad wording of §6.3.
- 2026-10-23 — **Jobs and API.** `python -m app.cli ingest --manifest ...` creates
  a job and runs it inline. `POST /v1/documents` accepts one file plus metadata,
  stores the bytes under `data/uploads` by SHA-256, creates a queued job, and runs
  ingestion as a FastAPI background task. `GET /v1/documents` supports
  `doc_type`, `source_agency`, `year_min`/`year_max` and pagination;
  `GET /v1/documents/{id}` adds chunk count; `GET /v1/jobs/{id}` exposes status,
  error and the JSON report. Uploads are in-process background tasks, not a
  durable queue; a process crash can leave a job `running`. That limitation and
  upload retention/cleanup are deferred to platform hardening.
- 2026-10-23 — **Report.** The job report contains document counts, total chunks,
  a Pandas-derived chunk-length summary (count/min/p50/p90/max/mean,
  approximate tokens), per-document summaries, duplicates, per-document failures,
  rejected manifest rows and duration. Failures and duplicates do not leak
  document text into logs or API errors. A malformed manifest fails the job; a
  bad individual document is reported and the rest of the manifest continues.
- 2026-10-23 — **Logging safety.** Ingestion and request failures log exception
  types, job ids and filenames only, never exception text. SQLAlchemy/asyncpg
  errors can embed SQL parameters (including chunk text), so tracebacks for
  unexpected database failures are deliberately not rendered. Expected failures
  use the safe reasons in the job report.
- 2026-10-23 — **Vector-store contract.** `app/store/base.py` defines a shared
  `VectorStore` Protocol (`upsert`, `search`, `delete_document`, `count`),
  `VectorRecord` with document metadata and `SearchFilters`
  (`doc_type`, `source_agency`, `year_min`, `year_max`). `PgVectorStore` uses the
  canonical Postgres chunk table and an HNSW cosine index
  (`ix_chunks_embedding_hnsw`, migration `0003`). `QdrantStore` creates a cosine
  collection with 384 dimensions, stores chunk text and document metadata in
  point payloads, and applies the same filters with Qdrant conditions. Both
  return `SearchHit` objects with cosine similarity scores. `PgVectorStore`
  computes `1 - cosine_distance`; Qdrant uses `Distance.COSINE`. Embeddings are
  L2-normalized, so both scores are on the same `[-1, 1]` scale and higher is
  better. The score-parity test compares the two stores on the same records and
  query. `top_k` is capped at 50 by `MAX_TOP_K` in both stores and the API
  schema.
- 2026-10-23 — **Ingestion fan-out and repair.** The pipeline writes document
  metadata and chunks atomically in Postgres, with chunks going through
  `PgVectorStore.upsert_chunks` inside that transaction. If
  `LABDOCS_VECTOR_BACKEND` is `qdrant` or `both`, Qdrant is updated after the
  Postgres commit. A duplicate content hash normally skips extraction/embedding,
  but still replaces the existing chunks in configured external stores, so
  re-ingesting repairs a missing or stale Qdrant index. Updates replace points
  after the Postgres transaction commits. There is no outbox: a Qdrant failure
  leaves the Postgres document in place and the job reports the failure;
  re-running the same input is the recovery path. This is deliberate for
  milestone 3 and avoids claiming exactly-once cross-store writes.
- 2026-10-23 — **Search API.** `POST /v1/search` accepts `query`, `top_k`,
  optional nested `filters` and an optional `backend` override (`pgvector` or
  `qdrant`). It embeds the query with the configured embedder, selects a
  configured store and returns scored chunks plus document metadata and latency.
  The default backend is `pgvector`; `LABDOCS_VECTOR_BACKEND=qdrant` makes Qdrant
  the default, while `both` keeps pgvector as the default and enables Qdrant
  fan-out. The qdrant backend is only selectable when it is configured; an
  unavailable store or embedding failure returns a safe 503 envelope.
- 2026-10-23 — **Synthetic fixture only.** `data/sample/` is clearly labelled
  synthetic and contains a PDF, Markdown, TXT, a byte-identical Markdown copy and
  malformed manifest rows. Its expected first run is 3 unique documents/1
  duplicate; its second run is 0 new/4 duplicates. It is not corpus content and
  must never be used for evaluation numbers or README claims. `data/corpus/` and
  `data/uploads/` are gitignored.

### Milestone 3 conditions (2026-10-25)

- **Filtered HNSW under-return (condition 3).** pgvector 0.8.7 applies SQL
  filters after the HNSW candidate scan, so a selective filter can return fewer
  rows than exist. The pre-fix reproduction used 500 synthetic documents with 5
  chunks each (2,500 chunks), a filter matching five chunks, `top_k=50` and
  `enable_seqscan=off`; it returned 0. Filtered searches now set
  `hnsw.iterative_scan = 'relaxed_order'`. If the approximate result still has
  fewer rows than `top_k` and the exact matching count is larger, the store
  retries with a forced sequential scan (`enable_seqscan=on`,
  `enable_indexscan=off`, `enable_indexonlyscan=off`,
  `enable_bitmapscan=off`). The same reproduction now returns 5/5. The fallback
  prioritizes correctness for rare filters and only runs on observed
  under-return.
- **Reindex CLI (condition 5).** `python -m app.cli reindex --backend qdrant`
  rebuilds the configured Qdrant collection from the canonical Postgres chunks.
  It deletes and recreates the collection, then upserts every document's
  records. It is a rebuild, not an atomic cross-store transaction; a failure
  during the rebuild leaves a partial collection and should be retried.
- **Startup checks (condition 5).** Startup rejects a configured
  `LABDOCS_EMBEDDING_DIMENSION` that differs from the database vector
  dimension, an embedder whose dimension differs, a Qdrant collection whose
  dimension differs, and a Qdrant collection whose distance is not cosine. The
  Qdrant collection is created or validated during startup when that backend is
  configured. Tests exercise the store checks and the real application
  lifespan.
- **Validation (condition 5).** `top_k` is bounded to 1–50 in the API and both
  stores. Unknown fields in the search request and nested filters return HTTP
  422 (`extra="forbid"`), rather than being silently ignored.
- **Failure injection and lifespan wiring (condition 5).** A Qdrant wrapper
  fails the first fan-out write; the Postgres document remains committed, the
  job fails with a safe error, and a duplicate re-ingest repairs Qdrant. A
  real-lifespan test starts the application with Postgres, Qdrant and a fake
  embedder, uploads through the API and searches through the Qdrant backend.

### Milestone 3 follow-ups (2026-10-25)

- **Real corpus is the only corpus.** The earlier temporary corrected manifest
  was discarded after the user fixed `data/corpus/manifest.csv`. The validation
  database `labdocs_conditions` and collection `labdocs_conditions_chunks` were
  deleted. The main database and Qdrant collection were cleared and re-ingested
  from the real manifest: 8 documents / 238 chunks on the first run, 0 new
  documents / 8 duplicates / 238 points on the second. Boilerplate stripping
  changed the chunk count from the earlier 249 to 238.
- **Metadata-only updates.** For a duplicate with the same
  `(source_agency, filename)` identity, changed `title`, `doc_type`, `year` or
  `version` values update the `documents` row and the Qdrant payloads through
  `set_payload`. Chunk rows, chunk IDs, text and vectors are untouched and the
  embedder is not called. The report includes `documents_metadata_updated` and
  a `metadata_updates` list with `document_id`, `filename` and
  `changed_fields`. A content-hash duplicate with a different identity is still
  a duplicate of the original document; renaming or changing the agency creates
  a new identity rather than mutating the old one.
- **Relaxed-order sorting.** `hnsw.iterative_scan = 'relaxed_order'` is used for
  filtered pgvector searches, then all final hits are re-sorted by score
  descending. The fallback exact scan uses the same final sort. A unit test
  exercises the sort helper with deliberately unordered scores.
- **pgvector version gate.** Compose and CI pin
  `pgvector/pgvector:0.8.7-pg16`. Startup and the ingest/reindex CLI call
  `ensure_iterative_scan_supported`, which rejects a missing extension or a
  version older than 0.8.0 with a clear error instead of silently losing
  filtered results.
- **Boilerplate stripping.** PDF extraction removes cross-page print furniture
  before chunking: browser print date/title headers, standalone URLs and page
  numbers, eCFR "up to date as of" and running headers/footers, the FDA
  "Contains Nonbinding Recommendations" header, and the OSHA navigation/footer
  block. The detector also removes short lines repeated on at least 60% of pages
  (minimum three), with digit-insensitive comparison so changing page numbers
  do not defeat it. Tests cover the patterns and preservation of body text.
  The real-corpus audit is in
  [`docs/milestone-3-corpus-audit.md`](milestone-3-corpus-audit.md).
- **Post-commit failure message.** When Qdrant fails after the Postgres commit,
  the job error explicitly says Postgres committed the document and the Qdrant
  index is out of date, and recommends
  `python -m app.cli reindex --backend qdrant`. The safe error does not include
  the underlying exception text.

### Milestone 4 — LLM abstraction + RAG (2026-10-25)

- **Provider abstraction.** `app/llm/base.py` defines a small `LLMClient`
  Protocol with normalized `LLMMessage`, `ToolDefinition`, `ToolCall`,
  `TokenUsage` and `LLMResult` types. The OpenAI-compatible client (the default
  development target is Ollama at `http://localhost:11434/v1`), Anthropic
  client and Azure OpenAI client share bounded retry/timeout behavior for
  timeouts, transport errors, HTTP 429 and 5xx responses. Provider errors are
  reduced to one safe `LLMError`; response bodies are not copied into API
  errors. `FakeLLM` is scripted and deterministic, and the factory refuses the
  `fake` provider when `LABDOCS_ENVIRONMENT=production`.
- **Retrieval and grounding.** `POST /v1/ask` retrieves the configured `top_k`
  (default 8) with the existing filters and vector backends. If there are no
  hits or the best cosine score is below `LABDOCS_ABSTENTION_THRESHOLD`, the
  answer is an explicit insufficient-evidence response and the LLM is not
  called. Otherwise the prompt contains numbered sources with their chunk ids
  and asks for a strict JSON object:
  `{"answer": "...", "citations": ["chunk-id", ...]}`. The validator parses
  fenced or bare JSON, removes duplicate/unknown citation ids, and returns
  `grounded=false` with a reason (`invalid_json`, `empty_answer`,
  `invalid_citations`, `no_valid_citations` or `invalid_citations_removed`)
  when the contract is not met. The API returns the validated citations with
  title, page, snippet and score, plus input/output token usage and separate
  retrieval/generation latency.
- **Threshold evidence.** `eval/abstention_probe.jsonl` contains ten
  in-corpus and ten out-of-corpus questions. `eval/abstention_probe.py` embeds
  each question with the real `bge-small-en-v1.5` model and records the top-1
  score from both stores (`top_k=8`, no filters). The distributions are
  identical across pgvector and Qdrant to six decimals:

  | Group | n | min | p50 | max | mean |
  | --- | ---: | ---: | ---: | ---: | ---: |
  | In-corpus | 10 | 0.771839 | 0.813442 | 0.856611 | 0.818125 |
  | Out-of-corpus | 10 | 0.623460 | 0.692466 | 0.719895 | 0.683931 |

  The groups are separable: the highest out-of-corpus score is `0.719895` and
  the lowest in-corpus score is `0.771839`; their midpoint is `0.745867`. The
  configured threshold is **0.75**, leaving a `0.030105` margin above the
  highest out-of-corpus score and a `0.021839` margin below the lowest
  in-corpus score. This is a deliberately small, real-corpus calibration set;
  milestone 9 should replace it with a larger evaluation set and report the
  trade-off between false abstentions and ungrounded answers.

  | Question id | Group | Top-1 score |
  | --- | --- | ---: |
  | in-01 | in_corpus | 0.804808 |
  | in-02 | in_corpus | 0.822165 |
  | in-03 | in_corpus | 0.813082 |
  | in-04 | in_corpus | 0.771839 |
  | in-05 | in_corpus | 0.855630 |
  | in-06 | in_corpus | 0.855347 |
  | in-07 | in_corpus | 0.778967 |
  | in-08 | in_corpus | 0.856611 |
  | in-09 | in_corpus | 0.809000 |
  | in-10 | in_corpus | 0.813801 |
  | out-01 | out_of_corpus | 0.694285 |
  | out-02 | out_of_corpus | 0.652835 |
  | out-03 | out_of_corpus | 0.696531 |
  | out-04 | out_of_corpus | 0.701634 |
  | out-05 | out_of_corpus | 0.690648 |
  | out-06 | out_of_corpus | 0.719488 |
  | out-07 | out_of_corpus | 0.719895 |
  | out-08 | out_of_corpus | 0.677515 |
  | out-09 | out_of_corpus | 0.663020 |
  | out-10 | out_of_corpus | 0.623460 |

### Milestone 5 — bounded tool-using agent (2026-10-25)

- **Hand-rolled loop.** `app/agent/loop.py` owns the message history and calls
  `LLMClient.chat` directly; there is no agent framework or hidden planner. The
  loop is hard-capped at **5 tool steps** (`AGENT_MAX_STEPS` is validated at
  `1..5`, and the loop clamps programmatic callers as well). Every model and
  tool call has a per-step timeout (`AGENT_STEP_TIMEOUT_SECONDS`, default 20s),
  and the whole run has `AGENT_TOTAL_TIMEOUT_SECONDS` (default 60s). When the
  step or time budget is exhausted, the loop makes one final no-tools synthesis
  call and returns the best partial answer with `partial=true` and
  `partial_reason` set; it never starts another tool loop.
- **Two tools.** `search_documents` uses the same `Retriever` as `/v1/search`
  and returns chunk ids, titles, pages, scores and short excerpts.
  `query_metadata` loads document metadata through SQLAlchemy, filters and
  sorts it with Pandas, and returns structured document rows. Both tools use
  Pydantic argument models with `extra="forbid"`, bounded years/top-k/limits,
  and enum sort fields; raw SQL is never built from model output. Request-level
  filters are defaults for both tools. Tool output is capped at
  `AGENT_MAX_TOOL_OUTPUT_CHARS` and marked `truncated` in the trace summary.
- **Trace and grounding.** Each executed tool call produces one trace entry
  with its step number, validated arguments, result summary, latency and safe
  error code. The final answer must be the same JSON contract as `/v1/ask`;
  citations are validated against the union of chunks returned by
  `search_documents`, so the model cannot cite an unseen chunk. Metadata-only
  answers may return no citations, but are then reported as ungrounded rather
  than inventing one.
- **API.** `POST /v1/agent/run` accepts a query, optional filters and a backend
  override, and returns the answer, citations, grounded verdict, full trace,
  step count, partial flag/reason, token usage and total latency. It requires a
  read-scoped key and maps provider failures to the same safe `502
  llm_unavailable` envelope as `/v1/ask`.
- **Tests.** Tests cover multi-step trace and citation validation, the
  step-limit partial path, model timeout fallback, Pandas metadata filtering
  and sorting, invalid tool arguments, search filters, output truncation, API
  auth/validation/backend errors, and provider failure mapping. The Anthropic
  adapter groups multiple tool results into one user turn as required by that
  API.

### Milestone 6 — compliance gap checker (2026-10-25)

- **Segmentation.** `app/gapcheck/segment.py` normalizes line endings and
  whitespace, drops cross-page furniture, signature blocks, revision tables and
  other boilerplate, then returns a Pandas DataFrame with exactly
  `clause_id, section, text, char_start, char_end`. Headings and numbered items
  start clauses; paragraph continuations stay with their clause. Clause ids are
  stable within a run (`SOP-001`, `SOP-002`, ...), and every `char_start` /
  `char_end` pair slices the normalized text exactly. The default hard cap is
  **80 clauses**; a larger SOP is rejected with `422 clause_cap_exceeded`
  rather than silently truncated. Empty/boilerplate-only SOPs are rejected with
  `422 invalid_sop`.
- **Direction A, SOP to regulation.** Each clause retrieves `top_k` regulation
  chunks with the request filters and the selected backend. If no hit reaches
  `GAPCHECK_RELEVANCE_THRESHOLD` (default **0.60**), the finding is
  `not_covered_by_corpus` and the LLM is not called. Otherwise the judge returns
  `compliant`, `partial` or `conflict` with cited chunk ids and a rationale.
  Citations are accepted only when they are in the retrieved set; an invalid
  judgement is retried once and then reported as `judge_failed` with no
  invented citation. The judge prompt treats the SOP and regulation text as
  delimited untrusted data, and a prompt-injection test verifies that SOP text
  cannot add citation ids or force a compliant verdict.
- **Direction B, regulation to SOP.** The chunks that passed Direction A are
  deduplicated. A whole-SOP scope retrieval then keeps only chunks belonging to
  the top `GAPCHECK_GLOBAL_TOP_DOCUMENTS` (default **2**) documents; this stops
  a generic clause such as “this SOP describes electronic records” from pulling
  unrelated Part 58 laboratory-space requirements into the omission analysis.
  Obligation sentences are extracted deterministically (mandatory `shall` /
  `must` / `is required to`; advisory `should`), deduplicated, and capped at
  **120 requirements**. Each requirement is compared with the best
  `GAPCHECK_SOP_MATCH_TOP_K` (default 3) SOP clauses using an ephemeral
  in-memory NumPy index. The judge returns `addressed`, `partially_addressed` or
  `missing`; addressed/partial citations must be shown SOP clause ids, while a
  missing verdict must have no citations. The report cites the regulation chunk
  that supplied the requirement.
- **Judge cache.** `gapcheck_judgement_cache` persists only validated
  judgements, keyed by a SHA-256 over the namespace (provider/model), prompt
  version, judgement kind, clause/requirement text and the candidate source
  ids/text. The runner also keeps a bounded in-memory LRU. Cache hits are
  counted in report metadata and cost no LLM tokens. Prompt version
  `gapcheck-judge-v3` adds explicit negation/scope and no-inference guidance;
  changing it invalidates old cache entries. SOP text is never logged; errors
  log only a job id and exception type.
- **Severity and report.** Severity is rule-based in
  `app/gapcheck/report.py`, never chosen by the LLM: `conflict`, or `missing`
  against a mandatory requirement, is **high**; `partial` /
  `partially_addressed`, or any finding against an advisory requirement, is
  **medium**; everything else is **low**. Findings are numbered `GAP-0001` in
  report order, include direction, verdict, severity, SOP clause refs,
  regulation citations with title/page/snippet/score, rationale and a
  “Suggested fix (not legal advice)” string. Reports carry the fixed banner
  “Decision support only, not legal advice...”, counts by verdict/severity/
  direction, `caps_hit`, and metadata (model, backend, filters, duration, token
  usage, clause/requirement totals, threshold, global document ids, cache hits,
  judge failures, caps).
- **Jobs and API.** `POST /v1/gapcheck` accepts exactly one of an SOP file
  (`.pdf`, `.md`, `.markdown`, `.txt`) or pasted text, plus optional
  `doc_type`, `source_agency`, `year_min`, `year_max` and backend. It returns
  `202` with a job id. `GET /v1/gapcheck/{job_id}` returns progress and, when
  complete, the report; another API key receives `404`. Progress phases are
  `queued`, `clauses`, `requirements`, `finalizing`, then a terminal
  `completed`, `failed` or `cancelled`. `POST /v1/gapcheck/{job_id}/cancel`
  (an addition beyond the two routes named in `SEED.md`) sets a cooperative
  cancellation flag; the runner stops between bounded steps and reports
  `cancelled`. Jobs live in `gapcheck_jobs`; lifecycle/progress persistence and
  background execution follow the ingestion-job pattern.
- **Caps and limits.** Defaults are 80 clauses, 120 requirements, 200,000
  tokens, 200,000 SOP characters, top-k 5, judge concurrency 4, retrieval
  concurrency 8, judge output 512 tokens and one active job per API key. A
  per-key overflow returns `429 gapcheck_limit` with `Retry-After: 30`. The
  clause cap is a request validation failure; requirement and token caps are
  recorded in `caps_hit` and the report instead of truncating silently.
- **Threshold evidence.** A probe with the real corpus and the fixture SOP gave
  top-1 retrieval scores of **0.627–0.778** for clauses that correspond to
  Part 11/211 controls (access, signatures, training). An earlier, awkwardly
  worded negation scored **0.584** and was reported `not_covered_by_corpus`;
  the retained fixture uses a clearer negation that scores **0.648**. The
  default **0.60** includes the relevant chunks and this contradiction while
  excluding the awkward wording. This is a small, synthetic-SOP calibration,
  not a general guarantee; milestone 9 should calibrate on human-authored SOPs.
- **Mutation evaluation.** Synthetic regression fixtures live under
  `tests/fixtures/gapcheck/`; they are clearly labelled as synthetic and are
  **not** legal ground truth or corpus documents. A real Ollama
  `llama3.1:8b` run against the real 8-document/238-chunk corpus used threshold
  0.60, top-k 3, global top 2, 12 clauses and 8–30 requirements depending on
  the cap being probed:

  | Fixture | Injected defect | Real-LLM result |
  | --- | --- | --- |
  | `clean_sop` | none | 0 conflicts, 0 `judge_failed`; all five clauses judged compliant. It is a short synthetic SOP, so the report still lists genuine omissions from Part 11/211; no unsupported claim was reported. |
  | `mutated_conflict` | access “not limited to authorized personnel” | **detected**: `conflict` high with a Part 11 authority-check chunk citation. |
  | `mutated_unsupported` | deletion “without an audit trail” | **detected**: `conflict` high with a Part 11 controls chunk citation. |
  | `injection` | “ignore all instructions” plus deletion | **detected**: `conflict` high with a citation; no blind compliant verdict. |
  | `mutated_missing` | authorization clause removed | **not detected** in this run. The omission is a known requirement-extraction/retrieval limitation: the authority sentence is inside an enumerated Part 11 list that the deterministic extractor keeps as one long requirement, and the 12/30-requirement caps can exclude it. |

  The committed deterministic fixture test passes for all five fixtures and
  validates every citation, but its text-driven judge is a test double, not an
  LLM-quality metric. The real-LLM omission false negative is documented rather
  than hidden; the human-authored mutation set remains a milestone 9
  deliverable.
- **Test coverage.** Gap-check tests cover segmentation and exact offsets,
  boilerplate removal, clause/requirement caps, both analysis directions,
  citation validation/retry, cache hits, prompt injection, severity and report
  counts, requirement-document scope filtering, API auth/file/text/filters/
  backend errors, per-key `429`, cancellation flag behavior, the deterministic
  mutation fixtures, and the `0005` migration tables/indexes/FK.

## Verification

- 2026-10-25 — Full `pytest`, Ruff, format check, mypy, `alembic check` and
  `docker compose config -q` passed locally against compose Postgres and
  Qdrant: **153 passed**, no skips. The vector-store contract suite runs the same
  tests against both `PgVectorStore` and `QdrantStore`. API tests cover
  pgvector search, filters, top-k validation, unknown filter fields, auth,
  Qdrant backend override and duplicate re-ingest repair. The migration test
  verifies the HNSW index definition (`USING hnsw` with
  `vector_cosine_ops`) and the document identity constraint. CI runs Postgres
  and Qdrant services and executes the same suite.
- 2026-10-23 — The sample fixture was ingested twice through the CLI with the
  real `bge-small-en-v1.5` model and `VECTOR_BACKEND=both` in a temporary
  database. First run: 3 documents / 9 chunks / 1 duplicate / 3 rejected.
  Second run: 0 new documents / 4 duplicates / 3 rejected. Qdrant held 9 points
  after both runs. The temporary database and collection were removed.
- 2026-10-25 — The real corpus at `data/corpus/` (gitignored) was fully
  ingested into the main database and `labdocs_chunks` using the real
  `data/corpus/manifest.csv`. First run: **8 documents / 238 chunks**; second
  run: **0 new / 8 duplicates / 238 Qdrant points**. The validation database and
  collection were deleted. See
  [`docs/milestone-3-verification.md`](milestone-3-verification.md) for the
  ten-query comparison, score parity, HNSW reproduction, reindex and fan-out
  verification, and
  [`docs/milestone-3-corpus-audit.md`](milestone-3-corpus-audit.md) for the
  per-document chunk audit.
- 2026-10-25 — Ten hand-written queries were run against both stores with
  identical filters and `top_k=5` after the extraction change. All ten had
  **5/5 top-5 overlap** and no ordering disagreement. Across the 50 shared
  top-5 chunks, the maximum score difference was `1.5e-7` (mean `5.2e-8`). The
  verification record includes each query text and the first 200 characters of
  every top-three chunk.
- 2026-10-25 — Milestone 4 tests cover all three provider request/response
  adapters with `httpx.MockTransport`, retry and safe-error mapping, production
  refusal for the fake provider, JSON/fenced grounding parsing, invalid and
  unknown citation removal, abstention below/at the threshold, the `/v1/ask`
  happy path, 502 mapping, auth, query validation and backend validation. The
  threshold probe produced the distributions and per-question scores recorded
  above on both stores; the top-1 scores agree to six decimals across pgvector
  and Qdrant.
- 2026-10-25 — Milestone 5 tests cover a two-tool trace, validated arguments,
  citation validation against seen chunks, the step-limit partial answer,
  model-timeout fallback, Pandas metadata filters/sorting, invalid arguments,
  request-filter defaults, output truncation, API auth/query/backend errors,
  provider failure mapping, and Anthropic multi-tool-result grouping. The full
  suite was **124 passed** at the end of that milestone.
- 2026-10-25 — Milestone 6 adds deterministic tests for segmentation/offsets,
  boilerplate removal, clause and requirement caps, both directions, citation
  validation/retry, judge caching, prompt injection, severity/report counts,
  global requirement-document filtering, API file/text/filter/backend errors,
  per-key `429 gapcheck_limit`, cancellation, the `0005` migration and the
  synthetic mutation fixtures. The full suite is **153 passed**, no skips. The
  real Ollama mutation run is recorded in the milestone section; its
  `mutated_missing` false negative and the LLM timeouts are reported as
  limitations, not suppressed.

## Known limitations

- Approximate token counts are not the BGE tokenizer's counts.
- Qdrant fan-out is best-effort after the Postgres commit. There is no outbox or
  exactly-once cross-store transaction; a Qdrant failure is reported with an
  explicit "Postgres committed / Qdrant out of date" message and a `reindex`
  recommendation, and the duplicate re-ingest path repairs the missing points.
  Pgvector and Qdrant can therefore be temporarily inconsistent.
- The HNSW indexes use default build parameters. There is no recall/latency
  tuning or benchmark yet; evaluation belongs to milestone 9. Filtered
  pgvector searches may take the exact-scan fallback for very selective
  filters, trading latency for correctness.
- Search is dense-vector retrieval only. There is no hybrid/BM25 component or
  reranker yet. `/v1/ask` has a calibrated abstention threshold, but plain
  `/v1/search` deliberately returns scored results without hiding low scores.
- The abstention threshold was calibrated on 20 questions from one small
  corpus. It is a starting point, not a guarantee; milestone 9 owns a larger
  evaluation set and the false-abstention/ungrounded-answer trade-off.
- The LLM clients implement one completion per call with bounded retries, not
  streaming or provider-specific structured-output modes. Prompt-injection
  defenses rely on source delimiting and citation validation; documents are
  still untrusted input.
- Agent runs are not persisted. The trace is returned in the response only, so
  there is no run history, resumability or cross-request memory. The metadata
  tool loads the document table and filters it in Pandas, which is appropriate
  for the current corpus but not a substitute for indexed SQL filtering at
  large scale.
- Agent citations are chunk citations only. Metadata-only answers can be
  correct but are marked ungrounded because there is no document-level citation
  type yet.
- Gap-check omission recall depends on requirement extraction and on the
  remaining SOP clauses retrieving a chunk that contains the omitted
  requirement. In the real-LLM synthetic run, removing the authorization clause
  was not detected because the authority sentence sits inside a long enumerated
  Part 11 list and can be collapsed or pushed past the requirement cap. The
  deterministic fixture test covers the pipeline path, but the real omission
  false negative is a known limitation. Milestone 9 should replace the
  synthetic fixtures with human-authored SOPs and evaluate omission recall
  explicitly.
- Gap-check retrieval uses a single dense embedding pass per clause plus one
  whole-SOP scope query. There is no reranker, and the global top-two-document
  scope filter is a heuristic that can exclude an applicable regulation for a
  broad SOP. The 0.60 threshold was calibrated on a short synthetic SOP, not a
  human-authored set.
- Gap-check jobs use in-process background tasks. Progress and reports are
  persisted, but there is no durable queue, crash recovery or automatic retry;
  a process restart can leave a `running` job without a worker. Caps bound
  clauses, requirements and tokens, but there is no separate wall-clock job
  timeout.
- Gap-check findings are decision support only. The LLM judge can produce
  false positives/negatives, and `judge_failed` findings require manual review;
  the report banner and suggested-fix labels make this explicit.
- `reindex --backend qdrant` deletes and recreates the collection rather than
  swapping a temporary collection atomically. A failed rebuild can leave a
  partial Qdrant collection; retry the command.
- If Qdrant is configured, startup now requires it to be reachable and to have
  a compatible collection. A Qdrant outage therefore prevents application
  startup rather than surfacing only through `/readyz`.
- `/readyz` checks the database and the configured Qdrant backend. It does not
  force-load the lazy sentence-transformer model, so the first query can still
  pay model-loading latency.
- The low-level `PgVectorStore.upsert` updates records but does not remove stale
  chunks when supplied fewer chunks for an existing document. The ingestion
  update path and `reindex` handle replacement explicitly; callers using the raw
  store upsert must reconcile chunk indexes themselves.
- Upload ingestion uses in-process background tasks; no durable queue, retry or
  crash recovery yet.
- Uploaded source files are retained without a cleanup policy yet.
- There is no per-document rollback UI or retry endpoint; re-running the manifest
  is the recovery path and is idempotent.
- Document identity is `(source_agency, filename)`, while content identity is
  the global raw-byte SHA-256. Re-uploading identical bytes with a changed
  title, doc_type, year or version updates metadata in Postgres and Qdrant
  without re-chunking. Renaming a file or changing its source agency creates a
  new document rather than updating the old one. A changed file with the same
  agency and filename updates the existing document.
