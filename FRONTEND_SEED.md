# FRONTEND_SEED: a calmer, more capable frontend for Regulatory Docs Copilot

Upgrade the existing Vite + React + TypeScript app in `frontend/` from "working tabs" to a small, coherent web app with a real layout, a design system, honest status handling, and a proper report view for the gap checker. **Minimal, not basic**: few dependencies, no UI kit, but deliberate spacing, typography, states and accessibility.

This document is additive to `SEED.md`. Where they differ on the frontend, this document wins. Backend behaviour does not change unless section 9 says so.

---

## 1. Goals

1. Make every feature pleasant and understandable to a non-developer (a QA or regulatory person), not only to the author.
2. Close every frontend gap listed in `verification-report-2026-10-25.md` ("Frontend feature acceptance gaps" and the High-severity "Frontend hides material outcomes" item).
3. Make the app **honest**: slow local models, partial agent runs, `judge_failed` findings, weak grounding and rate limits must be visible, never silently swallowed.
4. Make the gap checker, the headline feature, the best-looking and most useful screen.
5. Keep it small: the app should still be readable by one person in an afternoon.

## 2. Non-goals

- No component library (MUI, shadcn, Chakra, etc.), no Tailwind, no CSS-in-JS runtime, no animation library.
- No global state library. Hooks, context for settings/auth, and a small `usePolling` / `useAsync` pair are enough. (Adding TanStack Query is allowed only if you can justify it in `docs/design.md`; the default answer is no.)
- No remote fonts, icons or scripts. The app must work fully offline on a local machine.
- No user accounts, no server-side sessions, no persistence of Q&A beyond the browser session.
- No backend rewrite. No streaming responses in this iteration.

## 3. Stack and dependencies

Keep: Vite, React, TypeScript, generated OpenAPI types, `openapi-fetch`.
Add (only these): `react-router-dom` (routing), `lucide-react` (icons, tree-shaken), `vitest` + `@testing-library/react` + `@testing-library/user-event` + `jsdom`, `@playwright/test`.
Styling: one `styles/tokens.css` (design tokens) plus CSS Modules per component. System font stack and a system monospace stack.
TypeScript `strict: true` must be enabled in the committed `tsconfig` (the review found it absent). Keep generated types in sync with `/openapi.json` and add an `npm run check:types` script that fails when they are stale.

## 4. Design language

Feel: a calm document workbench. Think reading-room, not dashboard.

- **Tokens** (`tokens.css`): colour roles (surface, surface-raised, border, text, text-muted, accent, success, warning, danger, info), spacing scale (4, 8, 12, 16, 24, 32, 48), radii (6, 10), a type scale (12, 14, 16, 20, 28), one shadow for overlays. Light and dark values, driven by `prefers-color-scheme` with a manual toggle in Settings stored in `localStorage`.
- **Palette:** neutral greys plus one accent. Severity and verdict colours are always paired with an icon and a text label (never colour alone). Check contrast: AA at minimum for text and for badge text on its background.
- **Layout:** left rail navigation on screens >= 900px, collapsing to a top bar with a menu on narrow screens. Content max-width about 920px for reading views, wider for the report table. The layout must work at 360px width with no horizontal page scroll (wide tables scroll inside their own container).
- **Motion:** only subtle (150ms fades/slides); everything respects `prefers-reduced-motion`.
- **Voice:** plain language. "Not enough evidence in the loaded documents" instead of internal codes. Raw codes remain available in a Details area.

```
+------------------------------------------------------------+
| [logo] Docs Copilot            ( key: local-testing . write ) [theme] |
+----------+-------------------------------------------------+
| Ask      |  page title + one-line description              |
| Search   |  ---------------------------------------------- |
| Agent    |  main content (cards, forms, results)           |
| Gap Check|                                                 |
| Documents|                          [ right drawer: source ]|
| Settings |                                                 |
+----------+-------------------------------------------------+
```

## 5. Shared building blocks (`src/components/ui/`)

Hand-written and small: `Button`, `IconButton`, `Field` (label + hint + error), `Select`, `Badge`, `Card`, `Tabs`, `Drawer` (right on desktop, bottom sheet on mobile, focus trap, Esc closes), `Banner` (info/warning/error), `Toast`, `Skeleton`, `EmptyState`, `Stat`, `CopyButton`, `Spinner`, `ElapsedTimer`, `Disclosure` (collapsible).
Domain components: `CitationChip`, `SourceCard`, `ScoreBar`, `VerdictBadge`, `SeverityBadge`, `ProviderChip`, `FilterBar`.

## 6. App shell, routing, auth and errors

**Routes** (bookmarkable, React Router): `/ask`, `/search`, `/agent`, `/gap-check`, `/gap-check/:jobId`, `/documents`, `/settings`. Default route `/ask`. A reload on `/gap-check/:jobId` resumes polling or shows the finished report.

**Header status pill:** shows the key name and effective scope (from `/v1/whoami`), plus a coloured dot for API reachability (`/readyz`). Clicking it opens Settings.

**Settings view**
- API base URL (default `/api`), saved in `localStorage`. API key field (password type, show/hide), saved in `sessionStorage` only, with a "Forget key" button.
- A **Validate** button calls `/v1/whoami` and shows name and scopes. Invalid key shows a clear error.
- A readiness panel that lists database, Qdrant and any other `/readyz` checks.
- Defaults: preferred backend (pgvector/qdrant), default `top_k` (1 to 50). Theme toggle.
- A short, honest note that pasting a key into a browser is a demo-grade approach.

**Scope awareness:** write-only actions (upload, ingest) are hidden or disabled with an explanation when the key is read-only.

**One error layer** (`src/api/errors.ts`): every API call goes through a wrapper returning typed results. Map the backend's error envelope `{error:{code,message,request_id}}` to an `ApiError` with `status`, `code`, `message`, `requestId`, `retryAfter`.
- 401: route to Settings with an explanatory banner.
- 403: "Your key doesn't allow this action".
- 422: show the field-level problem where possible.
- 429: show a visible countdown from `Retry-After`; re-enable the action when it ends.
- 502/503/504 and timeouts: plain explanation ("The language model took too long or is unavailable"), plus a Retry button.
- Network failure: "Can't reach the API at <base URL>".
- Every error UI has a "Copy details" button that copies status, code, message and request id.

**Long-running requests:** a local CPU model can take 30 to 180 seconds. Every request-heavy action shows an `ElapsedTimer`, disables resubmission, and offers **Cancel** (AbortController). A cancelled request is not shown as an error.

## 7. Views

### 7.1 Ask
- Large auto-growing textarea, Ctrl/Cmd+Enter to submit. A "Filters" popover (agency, document type, year range) and an "Advanced" disclosure (backend, `top_k`).
- Answer card: answer text with **numbered citation chips** that are parsed safely from `[n]` markers (split text into React nodes; never `dangerouslySetInnerHTML`). Clicking a chip opens the **source drawer** with that chunk: document title, agency, year/version, page, relevance score bar, and the chunk text with the cited passage visible.
- Status badges, with honest wording:
  - **Citations checked**: tooltip "Every cited source exists in the retrieved set. This does not prove the source supports the claim. Read the sources." (The review found `grounded=true` can coexist with a mismatched snippet.)
  - **Not enough evidence**: shown when the service abstained; includes the best score and a one-line explanation, no citations.
- "Details" disclosure: latency split (retrieve vs generate), token usage, model/provider if returned, request id.
- Actions: copy answer with citations as Markdown, "Ask again", "Open as search" (same query in Search).
- Session history: the last 10 Q&A in `sessionStorage` shown as a collapsible list; clear button.

### 7.2 Search
- Query, filters, backend selector, `top_k`. Results as `SourceCard`s with score bars, document metadata and page.
- **Compare backends** toggle: runs the same query against pgvector and Qdrant and shows two columns with an overlap badge ("5 of 5 shared"). This showcases the dual-store design.
- Empty, loading and error states.

### 7.3 Agent
- Question box and run button with elapsed timer and cancel.
- Result: a prominent banner if `partial` is true (with `partial_reason`, for example "stopped at the time limit; answer may be incomplete") and a clear label when `grounded` is false. No answer ever appears without its status.
- **Trace timeline:** one card per step with tool name, arguments (pretty JSON in a disclosure), result summary, latency, and a `truncated` marker when output was cut. A run with zero steps says so explicitly.
- Final answer with citation chips and the same source drawer as Ask.

### 7.4 Gap Check (hero screen)
Input
- Tabs: **Paste text** and **Upload file** (md, txt, pdf, with type and size validation matching the API).
- Regulation filters (agency, document type, year range). A line showing which documents are in scope.
- Start button; on submit navigate to `/gap-check/:jobId`.

Progress
- A stepper showing the job's phases (reading the SOP, checking each clause, checking each requirement, building the report) with counts such as "clause 12 of 40" and "requirement 31 of 120", plus elapsed time and **Cancel**. Show a banner if a cap was hit (clauses, requirements, tokens).

Report
- **Summary header:** stat tiles for High / Medium / Low findings, a segmented verdict bar (compliant, partial, conflict, missing, addressed, not covered, judge failed), and run metadata (models, backend, duration, tokens, caps hit).
- **Banner:** the fixed decision-support disclaimer from the API, always visible.
- **Filters:** severity, direction (SOP to regulation / regulation to SOP), verdict, free-text search. Findings sorted by severity then clause order. Filters are reflected in the URL query string.
- **Finding card/row:** id (`GAP-0001`), severity and verdict badges, a one-line rationale. Expanding shows a **side-by-side comparison**: the SOP clause (with its section name) on the left, the cited regulation snippets (document, page, snippet) on the right, then the rationale and the suggested fix labelled "Suggestion, not legal advice".
- `judge_failed` findings get a distinct "Needs manual review" treatment and are never counted as passes. `not_covered_by_corpus` is shown as its own neutral group ("Outside the loaded documents").
- **Export:** download the report as JSON and as Markdown (client-side blob download). A print stylesheet for a clean "Print / Save as PDF".
- Empty report ("no findings") is explained, not left blank.

### 7.5 Documents
- Table with title, agency, type, year, version, chunks; search box, filter chips, sort, and pagination controls.
- Upload drawer (write scope only): drag-and-drop or file picker, metadata form (title, agency, document type, year, version) with validation, then a progress panel polling the job every 2 seconds with visible polling failures.
- **Ingestion report view:** documents, chunks, duplicates, metadata updates and rejected rows with their reasons, plus a Qdrant-sync warning when the job says Postgres committed but Qdrant is out of date (suggest the reindex command in a copyable block).
- Empty corpus state with a clear call to action.

## 8. Quality bar

- **Accessibility:** semantic landmarks, labelled controls, visible focus rings, full keyboard operation including the drawer (focus trap, Esc, focus returns), `aria-live` regions for status changes and errors, no colour-only meaning, reduced-motion support.
- **Performance:** route-level code splitting; the initial bundle stays small (report the gzip size in the PR); no layout shift when results load (skeletons sized like content).
- **Security:** model and document text rendered as text only; no secrets in the bundle, URLs or `localStorage`; the API key lives in `sessionStorage` only and never appears in logs or error "Copy details" output.
- **Tests (Vitest + RTL):** error mapping (401/403/429/partial/timeout), citation-marker parsing, source drawer behaviour, report filtering and sorting, export functions, key validation flow, scope-aware UI, each view's loading/error/empty state with mocked `fetch`.
- **E2E (Playwright):** one smoke test against the running stack using the fake LLM provider: save and validate key, upload the sample document, ask and open a citation, run the agent, run a gap check, filter findings, export. Add a visual check step that saves screenshots at 1280px and 390px widths for every view.
- **CI web job:** `tsc --noEmit` (strict), lint, Vitest, generated-types freshness, production build. Playwright in CI is allowed to run only on the fake provider.

## 9. Backend interaction rules

- Use only existing endpoints. The generated types are the contract.
- If a view cannot be built without an API change (for example list pagination or a field the UI needs), **do not change the backend silently**. Record the need in `docs/design.md` under "Frontend API needs" with a proposed minimal change, build the UI to degrade gracefully, and report it at the next stop point.
- Do not change retrieval, grounding or scoring behaviour.

## 10. Milestones (each ends with passing build, lint, tests and a merged PR)

- **F0. Audit and plan.** Read the existing `frontend/`, list what is reused, what is rewritten, the file layout you will use, and open questions. Capture baseline screenshots of the current app. No code changes except enabling `strict`.
- **F1. Foundation.** Tokens, UI components, app shell, routing, Settings (validate key, readiness, defaults, theme), the unified error layer, `usePolling`/`useAsync`/`ElapsedTimer`/cancel. Tests for the error layer. **STOP for review with screenshots.**
- **F2. Ask and Search.** Citation chips, source drawer, status badges, filters, backend compare, history. Tests.
- **F3. Agent.** Trace timeline, partial/ungrounded banners, cancel. Tests.
- **F4. Gap Check.** Input, progress stepper, resumable job route, report with summary, filters, comparison view, exports, print stylesheet. Tests. **STOP for review with screenshots and a recorded run on the fake provider and, if available, the local model.**
- **F5. Documents.** Table, filters, upload drawer, ingestion report. Tests.
- **F6. Hardening.** Playwright smoke test and screenshots at both widths, accessibility pass (keyboard-only walkthrough, contrast check), bundle size report, CI web job, README frontend section, `docs/design.md` decisions.

## 11. Definition of done

- Every item in the verification report's "Frontend feature acceptance gaps" table is addressed or explicitly listed as blocked by an API need.
- A full browser walkthrough (key, upload, search, ask, citation, agent, gap check, export) passes via the committed Playwright smoke test.
- Unit tests, strict type check, lint, build and the types-freshness check pass locally and in CI.
- No view hides a failure: partial agent runs, `judge_failed`, abstention, rate limits and timeouts are all visible and tested.
- Screenshots of all views at 1280px and 390px are committed under `docs/screenshots/` and referenced in the README.

## 12. Working agreement for the agent

- Read this file, `SEED.md`, `docs/design.md`, the verification report and `local-testing.md` before starting. Do not re-litigate decisions made here.
- Work one milestone at a time; before each, state in 3 to 5 lines what you will build; after each, summarise changes, untested areas and surprises.
- Use feature branches and PR-style summaries as before. Do not leave a milestone with failing or skipped tests.
- Do not invent API fields. If a field is missing from the generated types, say so.
- Verify visually: run the app and look at real screenshots; do not claim a layout works without having rendered it.
- Treat all model and document text as untrusted input.
- Keep it small. Prefer deleting code to adding abstractions. If a feature here would need a new dependency not listed in section 3, stop and ask.
