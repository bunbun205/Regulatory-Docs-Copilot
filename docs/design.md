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
- 2026-10-23 — `/readyz` now checks the database. Qdrant and embedder checks will be added with those dependencies.
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
  extension and the three tables/indexes. HNSW indexing waits for milestone 3,
  where search and the vector-store contract are implemented.
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
- 2026-10-23 — **Synthetic fixture only.** `data/sample/` is clearly labelled
  synthetic and contains a PDF, Markdown, TXT, a byte-identical Markdown copy and
  malformed manifest rows. Its expected first run is 3 unique documents/1
  duplicate; its second run is 0 new/4 duplicates. It is not corpus content and
  must never be used for evaluation numbers or README claims. `data/corpus/` and
  `data/uploads/` are gitignored.

## Verification

- 2026-10-23 — Full `pytest`, Ruff and mypy suite passed locally against compose
  Postgres. The sample fixture was also ingested twice through the CLI with the
  real `bge-small-en-v1.5` model: first run 3 documents / 9 chunks, second run 0
  new documents / 4 duplicates, with document and chunk counts unchanged and
  embeddings persisted as normalized 384-dimensional vectors.
- 2026-10-23 — The real corpus was supplied at `data/corpus/` with its
  `manifest.csv`; it remains gitignored. A smoke ingest of the six resolvable
  rows produced 191 chunks, and a second run produced zero new documents and six
  duplicates with the counts unchanged. Two OSHA rows were rejected as
  `file not found` because the manifest filenames omit the space present on disk
  (`Communication._` vs `Communication. _`, and `laboratories._` vs
  `laboratories. _`). The user-supplied corpus and manifest were left untouched;
  the rejection is reported through the real ingestion report rather than
  crashing the job.

## Known limitations

- Approximate token counts are not the BGE tokenizer's counts.
- No Qdrant/vector-store fan-out or HNSW index until milestone 3.
- Upload ingestion uses in-process background tasks; no durable queue, retry or
  crash recovery yet.
- Uploaded source files are retained without a cleanup policy yet.
- There is no per-document rollback UI or retry endpoint; re-running the manifest
  is the recovery path and is idempotent.
- The document identity is content, not filename: re-uploading identical bytes
  with new metadata is reported as a duplicate and the existing metadata is kept.
  A changed file with the same filename becomes a separate document.
