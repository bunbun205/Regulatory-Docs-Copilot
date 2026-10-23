# Design

Working notes and decision records for `labdocs`.

## Decisions

### Scaffold (milestone 0)

- 2026-10-23 — Python pinned to `>=3.12,<3.13` per SEED.md §5; `uv` provisions 3.12 (the system interpreter is 3.14).
- 2026-10-23 — Trunk `main`; the initial scaffold commit landed on `main`, feature work uses short-lived `feat/<milestone>` branches.
- 2026-10-23 — FastAPI 0.161.1 ships no `fastapi.mypy` plugin; mypy runs without it rather than pinning an older FastAPI.
- 2026-10-23 — Git remote configured after the scaffold: `origin` = `git@github.com:bunbun205/Regulatory-Docs-Copilot.git` over SSH. CI runs on GitHub Actions. (Supersedes the earlier "no remote configured" note.)
- 2026-10-23 — Docker CLI, daemon and Compose are now installed and the daemon is active. The local user is not in the `docker` group yet, so local compose use is blocked; tests use SQLite locally and Postgres in CI until that is fixed. `docker compose config` is validated in CI.
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
- 2026-10-23 — Tests run against SQLite+aiosqlite locally. CI sets `LABDOCS_TEST_DATABASE_URL` so the same API tests run against real Postgres, and runs `alembic upgrade head` against Postgres. No tests are skipped in either environment.

## Open questions

- Local Docker access needs the user added to the `docker` group (or a socket ACL) before compose can be used for development.
- `data/corpus/` and `manifest.csv` are user-supplied and are required before milestone 2 can ingest the real corpus.
