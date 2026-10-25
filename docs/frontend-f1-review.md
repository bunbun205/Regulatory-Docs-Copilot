# F1 review: foundation

Branch: `feat/frontend-f1-foundation`. Stop here for review before F2.

The unchanged baseline merged in [PR #9](https://github.com/bunbun205/Regulatory-Docs-Copilot/pull/9)
and the approved F0 audit merged in [PR #10](https://github.com/bunbun205/Regulatory-Docs-Copilot/pull/10),
each after both existing CI jobs passed. F1 remains unmerged for the requested
visual and behavior review.

## What changed

- Added a document-workbench shell: a desktop rail, mobile navigation panel,
  bookmarkable routes, default `/ask`, lazy views and skip-to-content link.
- Added light/dark/system tokens, scoped CSS Modules and hand-written UI
  primitives. The drawer traps keyboard focus, closes with Escape, makes the
  background inert and restores focus. Reduced motion is respected.
- Added Settings with key validation/effective scopes, password show/hide,
  Forget key, readiness checks, API base URL, backend/source-count defaults and
  saved theme. Keys remain in sessionStorage; preferences alone use localStorage.
  A key cannot be saved in the API address. Read-only keys cannot see uploads.
  The initial source count is two, matching the native CPU profile; users can
  save any whole-number default from 1 to 50.
- Added one typed request/error layer around `openapi-fetch`, including 401
  routing to Settings, safe details/copy, 403/422 explanations, Retry-After
  countdowns and transport timeouts. API errors and document/model content use
  React text nodes. Failed readiness checks remain visible even on HTTP 503.
- Added `useAsync` and `usePolling`: duplicate-submit prevention, local abort,
  stale-result protection, elapsed time, serialized polling and backoff. Local
  abort is labelled **Stop waiting**; gap server cancellation is **Cancel run**.
- Connected every existing view to Settings and shared request handling. The
  small bridge forms remain until F2–F5. All old explicit `any` uses are removed.
  Gap job URLs reload into polling or the existing report, without adding APIs.
- Added Vitest/RTL, Playwright, generated-types freshness, a no-new-warning lint
  gate and a 110 kB gzip initial-route budget check. All added direct dependencies
  are from the approved list. Unused global/template CSS and the fixed client
  are removed.

No production Python, provider, retrieval or grounding code is in this PR.
Unfinished local backend/platform/Docker changes remain outside it.

## Screenshots and visual checks

[Final screenshot index](screenshots/f1/README.md). The committed spec captures
all seven routes at **1280, 390 and 360px**, waits for each route's actual controls
and asserts no horizontal page overflow. Additional captures show invalid-key,
read-only, shared-error and dark states at the requested widths. Only the final
31-image set is committed.

Screenshots use the real app, Vite on 3100 and an API on 8001 built with the
existing app factory. Auth/readiness/document/job requests are real against an
isolated fake-provider API. Fixed test credentials and synthetic documents exist
only in `labdocs_frontend_test` and the matching Qdrant collection. The shared
502 error screenshot is explicitly a browser response fixture. The pre-seeded
completed gap job is a route fixture, not an evaluated compliance analysis.

Visual review caught an early capture showing the lazy-route skeleton instead
of the form; the spec now waits for route content. The final token-pair contrast
check also corrected a muted-text pair that was just below 4.5:1. The broader
accessibility walkthrough remains F6.

## Validation

| Check | Result |
| --- | --- |
| Vitest + React Testing Library | **47 passed**, no failures/skips |
| Playwright | **11 passed**, no failures/skips; actual route content at all three widths |
| Existing backend suite in a clean committed-backend checkout | **155 passed**, no failures/skips |
| Strict TypeScript | Pass for app, test and tool/config files |
| Generated types vs running clean API `/openapi.json` | Pass; exact regeneration comparison |
| Oxlint | No new warnings/errors; one existing Documents Date warning remains until F5 |
| Production build / route budget | Pass; approximately **95.8 kB gzip** initial `/ask` JS vs 110 kB budget |
| Security checks | Header-only key transport; no key in localStorage/URLs or copied error details; no remote requests in the route walkthrough |

[Recorded checks and sizes](verification/frontend-f1/checks.json),
[initial-route chunk sizes](verification/frontend-f1/bundle.json),
[backend JUnit](verification/frontend-f1/pytest.xml).
The size script sums unique JS files in the entry plus the default Ask route's
static import graph using Node gzip. Other routes remain lazy chunks.

The clean checkout deliberately excludes the unfinished platform changes.
The earlier workspace's 157-test count included two untracked hardening tests;
F1's clean-backend figure is 155. No new coverage or model-quality claim is made.

## Surprises and decisions

- The baseline TypeScript 6 dependency was outside `openapi-typescript` 7.13's
  declared `^5.x` peer range. TypeScript is now pinned to the supported 5.9 line;
  no `--force` or legacy-peer workaround is needed.
- Shared-client/polling migration removed the unused catch and effect warnings
  from Documents. The lint gate now allows only its one remaining Date warning;
  it rejects a reintroduction of the other warnings. F5 removes the last exception.
- A late 401 from an old saved key could invalidate a newly validated key.
  Generation/abort checks now protect bootstrap and explicit validation; a
  regression test covers that ordering.
- Readiness error bodies contain useful service checks outside the standard
  error envelope. The shared result keeps those values as `unknown`; Settings
  narrows them and displays the checks alongside the HTTP error.

## Reproduce

Use the existing Python environment and running local Postgres/Qdrant services.
The browser suite owns ports 8001 and 3100 during the run; stop manual servers
on those ports first. It refuses to reuse an arbitrary existing API.

```sh
cd frontend
npm ci
npm run typecheck
npm run lint
npm test
npx playwright install chromium
npm run test:e2e
npm run build
npm run check:bundle
```

`npm run check:types` compares against a running API on 8001, or the URL in
`LABDOCS_OPENAPI_URL`. The Playwright suite runs the same gate while its isolated
API is available. `frontend/e2e/server.py` is the only test entrypoint: it guards
and resets its dedicated `_test` database, uses its own `_test` collection and
temporary uploads, and never adds a production scripting flag. The full
upload/Ask/source/Agent/Gap/export journey remains F6.

## Untested and deferred

- F2 owns advanced Ask/Search controls, source drawers/chips, history, semantic
  citation presentation and backend comparison. F3 owns the richer Agent trace.
- F4 owns the complete Gap input/progress/report/filter/export/print UI; F5 owns
  Documents pagination/filters, upload drawer and ingestion report.
- F6 owns the full fake-provider journey, CI web job, all-view accessibility
  walkthrough, screen-reader coverage, large-corpus performance and final docs.
- F1 does not benchmark or validate local-model answer quality. Manual review
  uses the documented Qwen native profile; deterministic checks use the fake API.

Do not merge F1 or start F2 before the user's review reply.
