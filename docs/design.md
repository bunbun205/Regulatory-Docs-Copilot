# Design

Working notes and decision records for `labdocs`.

## Decisions

### Scaffold (milestone 0)

- 2026-10-23 — Python pinned to `>=3.12,<3.13` per SEED.md §5; `uv` provisions 3.12 (the system interpreter is 3.14).
- 2026-10-23 — Trunk `main`; the initial scaffold commit landed on `main`, feature work uses short-lived `feat/<milestone>` branches.
- 2026-10-23 — FastAPI 0.161.1 ships no `fastapi.mypy` plugin; mypy runs without it rather than pinning an older FastAPI.
- 2026-10-23 — Git remote configured after the scaffold: `origin` = `git@github.com:bunbun205/Regulatory-Docs-Copilot.git` over SSH. CI runs on GitHub Actions. (Supersedes the earlier "no remote configured" note.)
- 2026-10-23 — Docker CLI, daemon and Compose are installed and active. Docker group membership was added during milestone 2; existing shells need a new login or `newgrp docker` before they can reach the socket. `docker compose config` is validated in CI.
- 2026-10-23 — `qdrant/qdrant` pinned to `v1.20.0` (latest stable at the time) instead of `latest`; Postgres remains on `pgvector/pgvector:pg16`. Compose project is named `labdocs` and Postgres credentials are environment-overridable.
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
  Metadata-only changes (title, version, year) do not trigger a content update;
  they are reported as duplicates and the existing metadata is kept. For an
  update, the pipeline locks the document row, updates metadata, deletes all old
  chunks and inserts the new chunks in one Postgres transaction. After commit it
  deletes the document's points from Qdrant and inserts the new points. A
  shorter replacement document was tested and leaves no old chunks. If the
  external replacement fails, Postgres keeps the new content and the job fails
  safely; re-ingesting the same new content is a duplicate and repairs Qdrant.
  A duplicate re-ingest also replaces external points rather than merely
  upserting, so stale points for that document are removed.
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

## Verification

- 2026-10-25 — Full `pytest`, Ruff, format check, mypy, `alembic check` and
  `docker compose config -q` passed locally against compose Postgres and
  Qdrant: **82 passed**, no skips. The vector-store contract suite runs the same
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
  ingested into a separate validation database and Qdrant collection using a
  temporary corrected manifest. First run: **8 documents / 249 chunks**;
  second run: **0 new / 8 duplicates / 249 Qdrant points**. The original
  manifest still rejects two OSHA rows as `file not found` because its
  filenames omit the space present on disk (`Communication._` vs
  `Communication. _`, and `laboratories._` vs `laboratories. _`); the
  user-supplied corpus and manifest were left untouched. See
  [`docs/milestone-3-verification.md`](milestone-3-verification.md) for the
  ten-query comparison, score parity, HNSW reproduction, reindex and fan-out
  verification.
- 2026-10-25 — Ten hand-written queries were run against both stores with
  identical filters and `top_k=5`. All ten had **5/5 top-5 overlap** and no
  ordering disagreement. Across the 50 shared top-5 chunks, the maximum score
  difference was `1.0e-6` (mean `1.6e-7`). Reindexing Qdrant from Postgres
  reproduced the same top-5 sets. Full top-three results are in the verification
  record.

## Known limitations

- Approximate token counts are not the BGE tokenizer's counts.
- Qdrant fan-out is best-effort after the Postgres commit. There is no outbox or
  exactly-once cross-store transaction; a Qdrant failure is reported and the
  duplicate re-ingest path repairs the missing points. Pgvector and Qdrant can
  therefore be temporarily inconsistent.
- The HNSW indexes use default build parameters. There is no recall/latency
  tuning or benchmark yet; evaluation belongs to milestone 9. Filtered
  pgvector searches may take the exact-scan fallback for very selective
  filters, trading latency for correctness.
- Search is dense-vector retrieval only. There is no hybrid/BM25 component,
  reranker or score threshold yet.
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
  the global raw-byte SHA-256. Re-uploading identical bytes with new metadata is
  a duplicate and keeps the existing metadata. Renaming a file or changing its
  source agency creates a new document rather than updating the old one. A
  changed file with the same agency and filename updates the existing document.
