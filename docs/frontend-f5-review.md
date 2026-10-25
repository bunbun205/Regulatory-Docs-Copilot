# F5 review: Documents

Branch: `feat/frontend-f5-documents`. **Review stop: leave the F5 PR draft and unmerged.**
F4 passed final acceptance and merged in PR #14. All three jobs passed on its
main merge commit `b721b703638359304cd6b49f2209fef194b01d4b`:
[post-merge CI](https://github.com/bunbun205/Regulatory-Docs-Copilot/actions/runs/40229663356).
The [F4 acceptance review](frontend-f4-acceptance.md) records cancellation,
resumed polling, unresolved failures, safe rendering and complete evidence exports.

## Changes

- A Documents table with title/filename, agency, type, year, version and chunks.
  Existing server metadata/year filters and pagination use limit/offset/total;
  removable filter chips and page-size changes reset the page. Title search and
  sorting are explicitly **on this loaded page**, matching the existing API.
- Cached visible-row chunk counts use at most three concurrent detail requests,
  with a 200-document per-view cache. Obsolete page requests are aborted. A failed
  count shows a dash, preserves the row and offers retry; Refresh and terminal
  ingestion invalidate the counts. No invented list fields or endpoints.
- Write-scoped upload drawer with file picker and drag-and-drop, one-file/default
  size/extension validation, required metadata and API length/year bounds. Server
  validation remains authoritative. Read-only keys retain browsing/filtering.
- Accepted uploads close the drawer and show status in the library. Polling is
  serialized every two seconds, retains the last status on failure, exposes
  retry/details and stops on completed/failed. No ingestion cancel is invented.
- Report counters, duplicates, changed metadata fields, rejected rows/reasons and
  failed documents. A completed job can still need attention. Explicit supplied
  Postgres-committed/Qdrant-out-of-date errors show a copyable reindex command.
  Unknown report fields remain available in the full JSON disclosure; absent
  counters are omitted. Document/report text uses React text nodes throughout.
- Documents now owns its CSS; the final legacy wrapper and containment rules are
  removed. Warning-fatal Oxlint remains unchanged. No dependencies, production
  backend, provider, retrieval or grounding changes.

## Verification

**113 Vitest/RTL tests, 44 full-suite Playwright tests and 12 final Documents browser checks passed**, zero failures/skips. Strict no-emit TypeScript,
zero-warning lint, generated-type freshness and the production build pass.
The full browser suite and final Documents repeat are recorded in
[checks.json](verification/frontend-f5/checks.json). The browser suite includes
real Markdown uploads and duplicate/metadata updates through the Vite proxy,
app factory and isolated Postgres/Qdrant, including a real drag-and-drop upload
at 390px. Lifecycle/partial/rejection/sync-failure cases are explicitly synthetic
browser response fixtures, not claims that a real upload suffered those failures.
No tests or lint rules were weakened. Backend code is unchanged; its full
155-test suite passed in F4 acceptance and runs again in this PR's CI.

Initial `/ask` JS: **102,198 bytes gzip (102.2 kB)** against the 110,000-byte budget.
[Bundle report](verification/frontend-f5/bundle.json).

Every route and new Documents state is captured at 1280/390/360px with no
horizontal page overflow. Desktop/mobile table, upload, report, error and dark
captures were opened and inspected. The table deliberately scrolls inside its
own labelled, keyboard-focusable region on small screens. The upload drawer
scrolls vertically; separate captures include its action button.

[Final screenshot index](screenshots/f5/README.md).

| State | Desktop | Mobile |
| --- | --- | --- |
| Table | [1280px](screenshots/f5/documents-table-light-1280.png) | [390px](screenshots/f5/documents-table-light-390.png) |
| Filters | [1280px](screenshots/f5/documents-filtered-light-1280.png) | [390px](screenshots/f5/documents-filtered-light-390.png) |
| Upload | [1280px](screenshots/f5/documents-upload-ready-light-1280.png) | [390px](screenshots/f5/documents-upload-ready-light-390.png) |
| Upload actions | [1280px](screenshots/f5/documents-upload-actions-light-1280.png) | [390px](screenshots/f5/documents-upload-actions-light-390.png) |
| Actual ingestion report | [1280px](screenshots/f5/documents-actual-report-light-1280.png) | [390px](screenshots/f5/documents-actual-report-light-390.png) |
| Partial/sync fixture | [1280px](screenshots/f5/documents-partial-sync-report-light-1280.png) | [390px](screenshots/f5/documents-partial-sync-report-light-390.png) |
| Poll failure | [1280px](screenshots/f5/documents-poll-error-light-1280.png) | [390px](screenshots/f5/documents-poll-error-light-390.png) |
| Read only | [1280px](screenshots/f5/documents-read-only-light-1280.png) | [390px](screenshots/f5/documents-read-only-light-390.png) |
| Dark | [1280px](screenshots/f5/documents-dark-1280.png) | [390px](screenshots/f5/documents-dark-390.png) |
| Native corpus | [1280px](screenshots/f5/documents-native-light-1280.png) | [390px](screenshots/f5/documents-native-light-390.png) |

Actual upload/duplicate responses at each width are recorded under
[verification/frontend-f5](verification/frontend-f5/). Native library timings
and request concurrency are in [native-library.json](verification/frontend-f5/native-library.json).
All eight counts appeared in **456 ms at 1280px** and **351 ms at 390px**, with a measured maximum of **three** concurrent detail requests at both widths.
The native check reads the existing eight-document corpus without changing it
or making an LLM request; it is a small-corpus check, not a large-corpus benchmark.

## Surprises and remaining work

Visual inspection caught mobile table columns wrapping into very tall rows
although the page had no horizontal overflow. A minimum table width within the
scroll container, with dedicated year/chunk widths for long native metadata, fixes it, with a visible scroll hint and a scrolled-column
capture. Real drag-and-drop also exposed the picker still saying no file was
chosen; the dropped FileList now updates the picker and is asserted in Chromium.
After upload acceptance, focus moves to the job heading because the original upload opener is disabled during ingestion. The mobile regression exposed a race with drawer cleanup; focus now moves in the committed effect after that cleanup, with the assertions retained.
Duplicate ingestion legitimately reports zero newly ingested chunks while
retaining the document's existing chunk count; these are different quantities.

The earlier three legacy Documents lint warnings were already resolved in F1;
F5 introduces no warning suppression and keeps `--deny-warnings`.

**F6 follow-ups remain explicit:** PDF and TXT browser journeys; the combined
upload/Search/Ask/citation/Agent/Gap/filter/export journey and Playwright CI;
keyboard/screen-reader/contrast/reduced-motion accessibility review; large-corpus
pagination/chunk-count fan-out and long-report performance. Existing API needs
for global title search/sort, list chunk counts, capabilities and typed ingestion
reports remain documented in design.md. This milestone does not redesign them.

Stop for the user's F5 review. Do not merge this PR automatically or start F6.
