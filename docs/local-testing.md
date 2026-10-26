# Local development and verification

Use the [root quickstart](../README.md) for the packaged app on port 3000. A
service is not assumed to be running just because an earlier session started
it. Check `docker compose ps` or start the commands below explicitly.

## Native development

Prerequisites: Python 3.12 with uv, Node 24/npm, Docker/Compose and a configured
external generation provider or a local Ollama model. From the repository root:

```sh
cp .env.example .env  # Only on a fresh checkout; preserve an existing private file.
docker compose -f docker-compose.yml -f compose.dev.yml up -d postgres qdrant
uv sync --frozen
uv run alembic upgrade head
uv run python -m app.cli create-key --name local-browser --scope write
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Edit the private `.env` before starting the API. Native store addresses are
`localhost:5432` and `localhost:6333`; Compose container addresses are different.
A write key also has read access. Duplicate key names are rejected; save the
plaintext printed once by `create-key` and never put it in a committed file.
The browser's Settings page validates it and keeps it in sessionStorage.

In another terminal:

```sh
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 3000 --strictPort
```

The Vite proxy defaults to the native API. Set `LABDOCS_API_PROXY_TARGET` if you
choose another API port. `/readyz` checks Postgres, configured Qdrant and completed
embedding warmup. The initial model download requires internet; later runs can
use the cache. Generation-provider availability is checked by actual model calls,
not readiness.

Ingest public/approved corpus documents with a validated metadata manifest:

```sh
uv run python -m app.cli ingest --manifest data/corpus/manifest.csv
```

`data/corpus` is user supplied and ignored. The bundled `data/sample` files are
explicit synthetic fixtures; use `demo-manifest.csv` for three valid documents,
or `manifest.csv` to exercise duplicate/rejected rows. No synthetic results are
human-verified quality evidence.

## Optional Ollama

The production preparation uses external generation. For local development only,
set the compatible endpoint/model/key in `.env.compose` as shown in its example,
remove `LABDOCS_LLM_REASONING_EFFORT` if the model does not support it, and run:

```sh
docker compose --env-file .env.compose --profile ollama up -d ollama
docker compose --env-file .env.compose exec ollama ollama pull qwen2.5:7b
docker compose --env-file .env.compose --profile ollama up --build -d --wait --wait-timeout 600
```

For a host-installed Ollama, use its local endpoint in the native `.env` instead.
CPU generation can be slow or time out; inspect partial agent results and gap
judge failures. The 2026-10-25 [local audit](verification-report-2026-10-25.md)
records the earlier CPU experiments and limitations. It is historical evidence,
not a statement about current UI behavior or a reviewed quality benchmark.

## Required checks

Backend tests use a guarded database name ending in `_test`; never point the
test URL at the main corpus. The development init script creates `labdocs_test`
only on a fresh Postgres volume. For an existing volume, create that separate
database explicitly if it is absent. Browser tests create their own
`labdocs_frontend_test` database/collection and reset them.

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest --cov=app --cov-report=term-missing --cov-fail-under=80
uv run python -m eval.run --fixture
cd frontend
npm run typecheck
npm run lint
npm test
npm run check:types
npm run build && npm run check:bundle
npx playwright install chromium
npm run test:e2e
npm run test:performance
```

The native browser suite manages ports 8001 and 3100. It uses a separate
application factory, deterministic embedder/provider and fixed test keys; none
of these are selectable production flags. `fake` is rejected in production.

## Container browser gate

Use a distinct project and an explicitly isolated database. This tests the
production frontend image and nginx against the separate browser-test API image:

```sh
POSTGRES_DB=labdocs_frontend_test WEB_PORT=3300 docker compose -p labdocs-browser -f docker-compose.yml -f compose.test.yml up --build -d --wait
cd frontend
COMPOSE_BROWSER_URL=http://127.0.0.1:3300 FRONTEND_SCREENSHOT_MILESTONE=packaging npm run test:compose
```

Stop it with the same project/files using `down`. Its named volumes are separate
from the main `labdocs` project. The gate covers key validation, PDF/TXT ingestion,
search, cited answers, agent tools, gap reports/exports, mobile layouts, proxy
readiness, private metrics and the oversized-body error envelope.

Real quality evaluation is a separate operation. Follow
[the author-review guide](../eval/README.md); the default real-corpus command
returns status 2 while labels/SOP inputs remain unreviewed.
