# F0 review: frontend audit and implementation plan

Date: 2026-10-25. Branch: `feat/frontend-f0-audit`.

Read first: [design decisions](design.md),
[verification report](verification-report-2026-10-25.md) and
[local testing](local-testing.md). The approved decisions below control frontend work.
F0 was approved with the decisions below. F1 starts after the baseline and F0
PRs pass their checks and merge.

## Approved review decisions

- Snapshot the unchanged, unreviewed frontend on `chore/frontend-baseline`,
  excluding unfinished backend/platform/Docker work; scan every staged blob
  for keys and verify env/dependency/build ignores. Merge it, rebase F0 on main,
  then merge the focused F0 PR after checks pass.
- Omit optional provider/model chips when absent; describe unavailable values
  only in Details. Use bounded document-detail requests for chunk counts, but
  drop that column if slow. The other API fallbacks are accepted.
- The isolated FakeLLM entrypoint belongs entirely under `frontend/e2e/`, uses
  an `_test` database/collection and the existing app factory, and never adds
  a production scripting flag or changes provider/retrieval/grounding code.
- Introduce Playwright in F1. Commit a screenshot spec for every route at
  1280, 390 and 360px that asserts no horizontal page overflow. Extend it with
  each view; the full browser journey remains F6.
- Ask/Search/Agent use **Stop waiting** because server work can continue.
  Gap jobs alone use **Cancel run**.
- Keep initial route JS around **110 kB gzip**, lazy-load views and report
  gzip size in every PR. Keep Oxlint with no new warnings; F5 clears the three
  Documents warnings and then warnings fail the build.
- Commit only the final screenshot set for each milestone. Stop after F1
  with the specified shell/Settings/error screenshots and after F4 as agreed.

## PR-style summary

The current app has five working feature tabs, but no routing, Settings screen,
shared request lifecycle or responsive shell. This audit maps the replacement
work to F1–F6 and records the API limits before implementation.

F0 enables `strict: true` in both application and Vite TypeScript configurations.
It adds this plan, API needs, baseline screenshots and verification evidence.
There are no view, style, package, generated-type or backend code changes in F0.
No dependencies were added.

**Git surprise:** the starting branch was `main` at `2bdf9ea`;
the entire `frontend/`, FRONTEND_SEED, README and audit artifacts were untracked,
and several backend/platform files were already modified. Creating the F0 branch
preserved all of that work. The approved integration uses a separate unchanged
baseline PR before the small F0 changes; unrelated local work remains excluded.
See the PR summary for the resulting merge/check links.

## What exists and what will be reused

| Existing piece | Reuse | Rewrite / missing work | Owner |
| --- | --- | --- | --- |
| Vite, React, TypeScript, lockfile | Existing build and installed toolchain | Enable strict now; add only section-3 dependencies as needed later | F0/F1 |
| `src/types/api.ts` | Generated `paths`/`components`; live regeneration is identical | No manual edits; add generation/freshness scripts and a CI gate | F1/F6 |
| Vite `/api` proxy and nginx fallback | Same-origin API access; nginx already falls back to index.html | Test route reloads after routing; document alternate-base CORS limits | F1/F6 |
| `src/api.ts` | `openapi-fetch`, `X-API-Key`, sessionStorage key name | Replace fixed global client and no-op `authenticatedRequest` with typed result/error handling | F1 |
| `App.tsx` | Feature names and current endpoint coverage | Replace eager imports/local tab state with lazy routes, shell and Settings | F1 |
| `AskView` | Typed response, blank/pending guard, visible API errors, request ID fallback | Form, status wording, sources, filters, history, details, timer/cancel | F2 |
| `SearchView` | Typed endpoint and five-result default as initial behavior | Remove `any`; controls, compare, source cards and every request state | F2 |
| `AgentView` | Correct trace fields (`tool`, `arguments`, `result_summary`, `latency_ms`) | Remove `any`; status-first result, timeline, zero-step state, sources, timer/cancel | F3 |
| `GapCheckView` | Multipart submission, job polling endpoint, terminal status set, API disclaimer | Remove `any`; file/text modes, job routes, phases, report comparison, URL filters and exports | F4 |
| `DocumentsView` | Existing metadata fields, multipart upload and terminal job handling | Remove `any`; scope-aware drawer, pagination, reports, validation, errors and polling lifecycle | F5 |
| `main.tsx` | React StrictMode and root mounting | Mount router/settings providers; import tokens once | F1 |
| `index.css` | Lessons from the current layout; no visual framework | Replace global element rules with tokens and CSS Modules, with scoped table scrolling | F1–F5 |
| `App.css`, hero/template assets and template README/title | No product UI depends on `App.css` or the hero illustrations | Remove unused template code when the shell lands; replace frontend documentation/title | F1/F6 |

**Safety already present:** model/document strings use React text nodes or `pre`;
there is no `dangerouslySetInnerHTML`. Keys are in sessionStorage, not localStorage.
No remote resources were requested during the baseline walkthrough.

**Type safety gap:** strict mode passes, but four views still contain explicit
`any` (11 tokens including the explanatory comment). Each view rewrite replaces
these with generated types; generic API dictionaries are narrowed from `unknown`.
Strict mode alone is not evidence those data paths are safe.

## Current view audit

| View / concern | Observed baseline | Planned acceptance |
| --- | --- | --- |
| Shell / Settings | Five tabs; default Documents; no URLs, scope validation, theme, readiness or Settings | Default `/ask`; seven specified routes, including resumable gap jobs; read/write identity and API status; Settings storage/validation/defaults/theme |
| Shared errors | Ask catches API/network failures. Documents partly handles errors. Search/Agent/Gap discard most failures; poll errors disappear | One error/result layer, 401 redirect, 403 explanation, local field validation, 429 countdown, timeout/retry, redacted Copy details |
| Long actions | Ask guards duplicates; other forms/polls can overlap. No timers or AbortController | `useAsync` cancellation and stale-result protection; `usePolling` starts the next poll only after the previous one finishes; elapsed timer and terminal cleanup |
| Ask | Tiny textarea; plain answer/snippets; no interpretation of grounding or abstention | Auto-growing question, keyboard submit, filters/advanced options, checked-citation wording, excerpt drawer, details, source chips and last-ten session history |
| Search | Query, fixed top_k=5, title/score/text only | Controls, metadata/page, empty/error/loading, independent backend comparison and shared-chunk count |
| Agent | Plain answer and two-column trace; partial/grounded/error fields hidden | Partial/ungrounded banners before answer; zero steps explicit; accessible disclosures, trace error/latency and sources |
| Gap Check | Paste only; job id/status; flat findings; no counters, upload, filters or exports | Typed input/progress/report components, cancellation, resumable route, cap/manual-review states, comparisons, URL filters, downloads/print |
| Documents | Upload precedes library for every key; fixed first page; no report display | Library first, scoped pagination/filtering, explicit sort/search scope, read-only explanation and ingestion report |
| Accessibility | Main/nav exist, Ask is labelled; many labels lack associations, status regions and explicit focus treatment are missing | Labelled controls, live status, focus visibility, keyboard drawer/menu/tabs, reduced motion, contrast checks |

## Visual baseline

All **16 real Chromium screenshots** were captured and opened for inspection:
[screenshot index](screenshots/f0/README.md). Actual viewports are 1280×900 and
390×844, device scale 1. They show the existing app, not mockups.

The fake-provider API ran on 8001 and Vite on 3100 with the prescribed proxy.
The current corpus was listed without uploading/changing it. Input states were
captured without invoking generation; no local-model call is part of this audit.
The invalid-key image uses a real 401, not a mocked response. Password fields
mask the valid local key; the key is absent from artifacts and URLs.
After capture, the API was restored to the documented `qwen2.5:3b` manual
profile on 8001 and proxy readiness passed. No manual generation was submitted.

Desktop has ample unused space and very small query controls. The Documents
upload form pushes the library below the first viewport. At 390px the header
key/save controls and navigation run off-screen, and the document table expands
the page instead of scrolling inside a container. Every mobile capture has
horizontal page overflow. Observed page widths are approximately 497–501px for
the shell/input states and 722px for the populated Documents view. These are
baseline defects to fix; screenshot capture checks do not assert layout quality.

Settings does not exist, so its baseline is the header key/no-key/invalid-key
flow. Generation, traces, gap progress and reports are not represented by these
input screenshots; those receive real captures as their milestones land.

## Proposed file layout

Create files when their milestone needs them, not as empty scaffolding.

```text
frontend/
  src/
    main.tsx                    # router and settings provider
    App.tsx                     # shared shell / route outlet
    app/
      routes.tsx                # lazy route definitions
      SettingsProvider.tsx      # key/session settings and validated identity
      storage.ts                # non-secret preferences and bounded Q&A history
      AppShell.module.css
    api/
      client.ts                 # configured openapi-fetch + typed results
      errors.ts                 # unknown -> ApiError, headers, redaction
      contracts.ts              # narrow readiness/report dictionaries, multipart helpers
    types/api.ts                # generated; keep its existing location
    styles/tokens.css           # tokens, reset, themes, focus, reduced motion
    components/
      ui/                       # Button/Field/etc.; each with CSS Module as needed
      sources/                  # CitationChip, SourceCard, SourceDrawer, ScoreBar
      filters/                  # FilterBar with generated filter type
      status/                   # ProviderChip, VerdictBadge, SeverityBadge
    hooks/
      useAsync.ts
      usePolling.ts
      useElapsedTime.ts
    views/
      SettingsView.tsx
      AskView.tsx
      SearchView.tsx
      AgentView.tsx
      DocumentsView.tsx
      gapcheck/
        GapCheckInput.tsx
        GapCheckJob.tsx
        GapCheckProgress.tsx
        GapCheckReport.tsx
        FindingCard.tsx
        report-utils.ts         # pure sorting/filtering/export helpers
        print.css
      *.module.css              # styles stay beside the owning view
    test/                       # Vitest setup and typed fixtures
  scripts/check-types.mjs       # generate to temp, compare, clean up
  e2e/
    smoke.spec.ts
    screenshots.spec.ts
    server.py                   # test-only existing FakeLLM scripting if needed
  vitest.config.ts
  playwright.config.ts
docs/
  frontend-f0-audit.md
  screenshots/f0/               # current screenshots and observations
  screenshots/f1/ ... f6/       # later rendered evidence
```

`ui/` contains the small hand-written primitives named in FRONTEND_SEED §5.
No UI kit, Tailwind, remote fonts/scripts, animation or global state library.
Keep the existing Oxlint installation; adding ESLint or another tool would need
approval because it is outside §3. Add only the approved router/icons/test
packages in F1 and Playwright when a committed browser suite is introduced.
No TanStack Query is planned.

## Implementation sequence and review gates

| Milestone | Deliverable and checks | Branch / stop |
| --- | --- | --- |
| F0 | Audit/reuse map, API needs, strict configs, baseline screenshots and green existing checks | `feat/frontend-f0-audit`; **stop now for review** |
| F1 | Tokens/light/dark, responsive shell/menu, lazy routes, Settings/identity/readiness/defaults, primitives, shared errors/async/polling/timers/Stop waiting. Add approved Vitest/RTL and Playwright tooling; tests for errors, storage/key validation/scopes, async/poll timing and drawer focus. Add `check:types` and every-route screenshot/overflow checks at 1280/390/360px. Existing feature views remain operational inside the shell until replaced | `feat/frontend-f1-foundation`; **stop with shell, Settings valid/invalid/read-only and shared-error screenshots in light at 1280/390px, plus dark shell/Settings** |
| F2 | Ask/Search, filters/backend/top_k, safe marker splitting/fallback chips, source drawer, history/details and backend comparison. Tests for states, parsing, drawer keyboard/focus, independent compare failures and history limit | `feat/frontend-f2-ask-search` |
| F3 | Agent status-first answer, partial/ungrounded/zero-step states, trace disclosures, safe JSON arguments, cancel/timer and shared sources. Test partial reasons, errors, empty traces and abort behavior | `feat/frontend-f3-agent` |
| F4 | Gap input/upload, job route/resume/progress/cancel, report counts/verdicts/manual-review/neutral groups, comparisons, URL filters, JSON/Markdown/print. Test input limits, polling failures, cancelled/failed/empty jobs, sorting/filtering/export and untrusted text | `feat/frontend-f4-gap-check`; **stop with input/progress/report screenshots at both widths, a recorded fake run and a manual local-model run if available** |
| F5 | Documents filters/pagination, scoped sort/search, lazy detail chunk counts, scope-aware upload drawer, ingestion summary/rejections/sync warning. Test all states and metadata/file validation | `feat/frontend-f5-documents` |
| F6 | Committed fake-provider browser journey, all-view screenshots at both widths, 360px overflow check, keyboard-only walkthrough/contrast, bundle report, CI web gates and README/design decisions | `feat/frontend-f6-hardening` |

Each implementation PR reports changed behavior, test counts, untested areas,
surprises, screenshots and gzip size. Build, strict typecheck, existing lint,
Vitest and generated-type freshness must pass once the F1 tools exist. No
`skip`, `todo` or allow-no-tests flags are used to turn a missing test into green.
Do not merge a review-stop PR or begin the next milestone before the reply.

## API compatibility and graceful fallbacks

The complete inventory and minimal proposals are recorded in
[Frontend API needs](design.md#frontend-api-needs). No backend changes are part
of this frontend sequence. In particular:

- Pagination, metadata/year filters, document detail/chunk counts, file gap
  input and cooperative gap cancellation already exist. Use them.
- Ask/Agent/gap citations provide excerpts, not the full chunk or a support
  span. Label excerpts honestly; enrich document metadata via the existing
  detail route; do not substitute a different search hit as the cited text.
- Answer strings need not contain `[n]`. Parse only valid existing markers;
  otherwise show a numbered source list without manufacturing inline positions.
- Omit Ask/Agent model/provider chips when not returned; mention unavailable
  only inside Details. Gap metadata
  is a dictionary; narrow its values before display and preserve raw JSON export.
- `partial` and `grounded` are distinct from HTTP errors. Render their status
  regardless of whether the answer string is empty.
- Generic 422 errors have no field detail. Do client validation against known
  contract constraints; show unmatched server errors at form level.
- Stop waiting aborts Ask/Search/Agent requests locally. It does not prove the server
  or model stopped. Gap cancellation uses the actual cancel endpoint and polls
  until the server reports a terminal state. Ingestion has no cancel endpoint.
- Report caps are available on completion, not during progress polling. Do not
  claim progress-time cap detection that the API does not expose.

## Test approach and limitations

**F0 results:** full existing backend suite **157 passed in 21.83s**, zero
failures/skips; baseline browser audit **22 checks passed**, zero uncaught JS
exceptions and zero remote requests. Production build and strict configs pass.
Lint exits 0 with three existing Documents warnings (unused catch variable,
Date during render, state update in effect). Python lint/format/mypy pass.
Generated API types match live regeneration byte-for-byte. Initial JS gzip is
**73.65 kB**, CSS **0.65 kB**; all views currently share one eager JS bundle.
[Machine-readable evidence](verification/frontend-f0/checks.json),
[pytest result](verification/frontend-f0/pytest.txt),
[JUnit](verification/frontend-f0/pytest.xml),
[browser observations](screenshots/f0/baseline.json).

There is **no repository Vitest or Playwright suite yet**. F0 uses the available
temporary browser tooling and does not call the absent `npm test` command or
claim absent tests passed. Adding committed test tooling belongs to F1; adding
the complete browser smoke flow belongs to F6. F0 does not test future layouts,
drawers, themes, exports, screen readers, live-model answers or full browser
upload/Ask/Agent/Gap execution.

The existing factory's `fake` provider returns unscripted `Fake answer.` by
default. That cannot produce valid answer JSON/citations, tool traces or gap
judgements for the final smoke journey. Plan a **test-only startup fixture**
under `frontend/e2e/` that scripts the existing `FakeLLM` against actual source
IDs and uses an isolated `_test` database/collection and synthetic fixtures.
Do not alter provider/retrieval/grounding code or mock away the entire API and
call it an end-to-end test. Use browser response fixtures for UI states that
cannot be scheduled reliably, and label those screenshot fixtures explicitly.
Local `qwen2.5:3b` runs are manual checks, not CI success criteria.

## Resolved review points

1. **Git baseline:** the separate baseline PR and focused F0 PR are approved.
   Existing unrelated changes remain intact.
2. **API limits:** accepted with the optional-chip/count-column rules above. The excerpt/missing-metadata, page-scoped
   sort/search and cancellation fallbacks for this frontend-only effort. Any
   later backend improvement is separate work, not an implicit permission here.
3. **Deterministic E2E:** approved; use the test-only scripted FakeLLM harness described
   above. Until it exists, do not claim the stock fake startup can complete the
   success journey.

All other implementation choices follow FRONTEND_SEED and the sequence above.
The next review stop is F1; do not begin F2 before the user's reply.
