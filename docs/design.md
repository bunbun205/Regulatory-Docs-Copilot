# Design

Working notes and decision records for `labdocs`.

## Decisions

- 2026-10-23 — Project scaffold: Python pinned to `>=3.12,<3.13` per SEED.md §5 (the system interpreter is 3.14, so `uv` provisions the managed 3.12 toolchain).
- 2026-10-23 — Git repository initialised on trunk `main`; initial scaffold commit lands on `main` before any feature branches.
- 2026-10-23 — Docker CLI 29.9.2 is installed locally, but the daemon is not running and the Compose plugin is absent as of this scaffold. `docker-compose.yml` is authored and YAML-validated; booting Postgres/Qdrant is deferred until the daemon is enabled (required from milestone 2). This deviates from the stated environment assumption and is accepted for milestone 0 only.
- 2026-10-23 — No git remote is configured (per user instruction). Impact: GitHub Actions cannot run and "CI green" is verified by running the same ruff/mypy/pytest commands locally; PR-style summaries are recorded in-session. The CI workflow is committed for use once a remote exists.
- 2026-10-23 — FastAPI ships no `fastapi.mypy` plugin in the installed version (0.161.1); mypy runs without it rather than pinning an older FastAPI.

## Open questions

- Docker daemon/Compose plugin need to be enabled before milestone 2 (ingestion needs Postgres/Qdrant).
