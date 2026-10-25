# F4 review: Gap Check

Branch: `feat/frontend-f4-gap-check`. **Review stop: leave this PR unmerged.**
F1, F2 and F3 merged in PRs #11, #12 and #13 after green CI.

## What changed

- Paste/file input, PDF/Markdown/TXT extension and documented default size/text
  prechecks, regulation filters, backend selection, and debounced document-scope
  counts/titles from the existing list endpoint. Scope is described as the search
  scope rather than a promise that every document/requirement will be checked.
- Bookmarkable job routes resume polling and show the API's phases and clause/
  requirement counts, elapsed time and **Cancel run**. Cancellation is a request
  until the server confirms it; a normal cancelled run is explained without an
  error alert. Poll failures retain the last confirmed state and show an error.
- Reports show severity counts, all eight verdicts, a segmented bar, supplied
  metadata, reported tokens/caps and the API's decision-support disclaimer.
  Failed judgements remain unresolved with a separate manual-review count;
  outside-corpus findings appear in a neutral group. Missing/unknown metadata is
  narrowed safely and optional chips are omitted.
- URL-backed severity/direction/verdict/text filters, severity-then-clause sorting,
  expandable SOP/regulation excerpt comparisons and clearly labelled suggestions.
  JSON/Markdown downloads include the full report; Markdown escapes untrusted
  HTML/Markdown. Print uses the current selection, expands details, hides app
  navigation/controls and states the printed count/filter selection.

All endpoint/response use follows the generated types. No production backend,
provider, retrieval or grounding changes and no new dependencies are included.
The test-only scripted judge and synthetic report fixture live under frontend/e2e.
Unfinished local backend/platform/Docker work remains excluded.

## Validation and screenshots

**92 Vitest/RTL tests and 32 Playwright tests passed**, zero failures/skips.
The three export/print browser cases also passed a focused repeat after the
final duplicate-beforeprint restoration guard. Strict no-emit TypeScript, warning-fatal Oxlint (zero warnings), live-schema type
freshness and the production build pass. Initial `/ask` JS is **102,082 bytes gzip
(102.1 kB)** against the 110,000-byte budget. Backend checks remain the unchanged
155-test committed suite; the preserved two platform tests are explained in F1.

[Final screenshot index](screenshots/f4/README.md),
[checks](verification/frontend-f4/checks.json),
[bundle](verification/frontend-f4/bundle.json).
Every route and the research/Agent/Gap states are captured at 1280/390/360px with
no horizontal page overflow. Input, progress, report, comparison, manual review,
empty/error, file and cancellation screenshots were opened and inspected at
1280/390px. Only the final milestone set is committed. The print PDF was rendered
for visual inspection and contains all eight comparisons/rationales/suggestions.

| Review state | Desktop | Mobile |
| --- | --- | --- |
| Input | [1280px](screenshots/f4/gap-input-light-1280.png) | [390px](screenshots/f4/gap-input-light-390.png) |
| Actual fake-job progress | [1280px](screenshots/f4/gap-progress-light-1280.png) | [390px](screenshots/f4/gap-progress-light-390.png) |
| All-verdict report fixture | [1280px](screenshots/f4/gap-report-all-verdicts-light-1280.png) | [390px](screenshots/f4/gap-report-all-verdicts-light-390.png) |
| Actual fake-job report | [1280px](screenshots/f4/gap-real-report-light-1280.png) | [390px](screenshots/f4/gap-real-report-light-390.png) |
| Manual Qwen result | [1280px](screenshots/f4/gap-local-result-light-1280.png) | [390px](screenshots/f4/gap-local-result-light-390.png) |

## Recorded runs and interpretation

**Fake provider:** a real submitted/polled job used the existing app factory,
Postgres/Qdrant and scripted test-only judge against an isolated synthetic corpus.
The 1280px run reported **3.061 seconds** of analysis and was observed completed
at **5.099 seconds**; it returned one compliant, one addressed and one
outside-corpus finding, with no judge failures/caps. Independent runs at the
other widths, reloads and file-job cooperative cancellation also passed.
[Recorded 1280px run](verification/frontend-f4/fake-run-1280.json).
These scripts prove UI/job scaffolding, not model quality or regulatory accuracy.

The separate eight-verdict report is explicitly a **synthetic report fixture**,
not a model run. It exercises manual-review, outside-corpus, high/medium/low,
cap and export presentation. [JSON export](verification/frontend-f4/synthetic-report-export.json),
[Markdown export](verification/frontend-f4/synthetic-report-export.md),
[print PDF](verification/frontend-f4/synthetic-report-print.pdf).

**Native qwen2.5:3b:** the existing synthetic
`tests/fixtures/gapcheck/clean_sop.md` completed in **65.444 seconds** observed
through the browser; the API reported **61.827 seconds** of analysis. Scope used
matching 2003 FDA guidance metadata. A documented **three-requirement cap** bounded
this CPU manual run, with one 256-token judge at a time and the native 180-second,
zero-retry profile. The report explicitly contains `caps_hit: ["requirements"]`.
It returned **4 partial, 3 missing and 1 outside-corpus** findings, zero judge
failures. These are model outputs, not human-verified defects or a quality score;
some partial rationales concern generic purpose/training clauses and require
source review. [Settings, progress, full response and review notes](verification/frontend-f4/local-model-run.json).
The normal documented native profile is restored after recording the run.

For continuity, F2's manual Ask returned in **12.832 seconds**. Its two OSHA
excerpts were relevant, with only partial visible support because one excerpt
cut off before the listed requirements. [Recorded Ask and assessment](verification/frontend-f2/manual-ask.json).

## Surprises and untested areas

Browser testing caught rapid Clear filters → verdict selection restoring a stale
severity. A current-parameters ref fixes it, with unit and browser regressions.
Visual review also corrected the completed-reading phase copy, resumed elapsed
initialization and duplicate red cancellation message. The existing API needs
(full-chunk lookup, progress-time caps, capabilities and typed metadata) remain;
no additional backend change is required for this milestone.

PDF/TXT uploads were not driven through the F4 browser suite; the committed
browser upload uses Markdown, while extension/empty/size validation and existing
backend extraction checks cover the shared path. Full journey/Playwright CI,
screen-reader/accessibility walkthrough and large-corpus performance remain F6.
F5 Documents remains untouched beyond the already-approved foundation migration.
Stop here for the user's F4 review; do not start F5 or merge this PR.
