# Frontend development and verification

Vite/React/strict TypeScript with hand-written CSS Modules and generated OpenAPI
types. No remote fonts/scripts, UI framework, HTML/Markdown renderer or production
scripted LLM is used. Model and document strings stay text.

Install the locked Node dependencies with `npm ci`. With the native API on 8001,
run `npm run dev -- --host 127.0.0.1 --port 3100 --strictPort`; Vite proxies `/api`
to the API. Open Settings, validate a key, then use Documents, Search, Ask, Agent
and Gap Check. Keys stay in sessionStorage; preferences (never keys) use localStorage.
See the [root README](../README.md) and [design decisions](../docs/design.md)
for scope and backend limitations.

The local gates are `npm run typecheck`, `npm run lint`, `npm test`,
`npm run check:types`, `npm run build`, and `npm run check:bundle`. Type freshness
uses the running API by default, or `LABDOCS_OPENAPI_FILE` exported from the same
checked-out app factory. The initial Ask route has a 110,000-byte gzip JS budget.

`npm run test:e2e` starts Vite3100 and the separate test-only API8001 entrypoint.
Both ports must be free. It uses real Postgres/pgvector and Qdrant, guarded database
`labdocs_frontend_test`, a separate collection and temporary upload directory.
**Only those isolated test stores are reset.** Fixed test credentials and scripts
live under `e2e/`, never in the production factory. Install the matching browser
with `npx playwright install chromium` (CI also installs system dependencies).
The suite includes the combined keyboard journey, real PDF/TXT document and SOP
uploads, cancellation/resume/error states, data exports and print content checks.

`npm run test:performance` runs separately with the same isolated test entrypoint,
seeding 5,000 synthetic documents/10,000 chunks in both stores plus the one default
fixture. It measures page/count/filter/cache behaviour and a 1,000-finding report.
It must not run concurrently with the ordinary suite. Timings are observations,
not regulatory-quality metrics or production capacity claims.

Screenshots cover every route and state at 1280/390/360px, asserting no horizontal
page overflow. Tables scroll inside their own region. Test evidence is written
under `docs/screenshots/f6` and `docs/verification/frontend-f6`; only final local
captures are committed. Accessibility checks cover keyboard paths, visible text
contrast, reduced motion and Chromium accessibility-tree names. They do not claim
a human assistive-technology session or WCAG certification.
