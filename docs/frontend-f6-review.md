# F6 acceptance: frontend hardening

Branch: `feat/frontend-f6-hardening`. F5 PR #15 merged; all main jobs passed on
`b3e1e3a` ([CI](https://github.com/bunbun205/Regulatory-Docs-Copilot/actions/runs/40238985942)).
The user authorized autonomous merges after checks; no routine review stop applies.

## Completed checks

**113 unit tests, 53 full browser tests and 3 large-corpus browser tests passed**,
with zero failures/skips. Strict TypeScript, warning-fatal lint, generated-type
freshness from the clean running app factory and production build pass. Initial
Ask JS is **102,197 bytes gzip (102.2 kB)** against 110,000 bytes.
[Raw check record](verification/frontend-f6/checks.json).

- The committed combined journey starts without a key, validates it in Settings,
  uploads a real text-extractable PDF, waits for ingestion, searches, asks, opens
  a citation, runs the agent, reads its trace, runs Gap Check, filters and exports
  JSON/Markdown. Controls are operated with Tab/Shift+Tab/Enter and text input;
  browser automation supplies file bytes in place of a native OS file dialog.
- Separate real PDF and TXT journeys exercise document upload, SOP upload,
  progress, reload/resumed polling, report comparisons and both exports at all
  three widths. The files are explicitly synthetic test data, never a human
  ground-truth evaluation set. Test-only judge scripts cite actual retrieved IDs.
- Keyboard focus/trapping/Escape/return, Chromium accessibility-tree control names
  and assertive error live regions, light/dark routes, text/control/placeholder/
  boundary contrast and reduced motion are checked. No human screen-reader
  listening session or WCAG certification is claimed. Real assistive-technology
  user review remains an explicit limitation.
- Browser testing found a default dark placeholder at **3.41:1**; it now uses the
  existing muted-text token with opacity 1. Reduced motion now turns animations
  and transitions off completely. Contrast checks correctly exclude unpainted
  closed disclosure contents and wait for the selected theme.
- CI now runs the full browser suite and separate large-corpus checks using only
  the isolated fake-provider entrypoint. No production scripted-provider flag,
  dependency, backend/provider/retrieval/grounding changes are included.

[Final screenshot index](screenshots/f6/README.md). Every route and new state is
captured at 1280/390/360px with no horizontal page overflow. Desktop/mobile dark
reports, actual PDF/TXT comparisons and performance captures were opened and
inspected. Existing print tests still require every selected rationale/suggestion.

| New state | Desktop | Mobile |
| --- | --- | --- |
| Combined journey report | [1280](screenshots/f6/journey-report-dark-1280.png) | [390](screenshots/f6/journey-report-dark-390.png) |
| PDF comparison | [1280](screenshots/f6/file-pdf-gap-report-1280.png) | [390](screenshots/f6/file-pdf-gap-report-390.png) |
| TXT comparison | [1280](screenshots/f6/file-txt-gap-report-1280.png) | [390](screenshots/f6/file-txt-gap-report-390.png) |
| Dark error | [1280](screenshots/f6/accessibility-error-dark-1280.png) | [390](screenshots/f6/accessibility-error-dark-390.png) |
| Large corpus | [1280](screenshots/f6/performance-library-1280.png) | [390](screenshots/f6/performance-library-390.png) |

## Large-corpus measurements

Both real isolated stores contain **10,001 chunks** across **5,001 documents**
(the 5,000-document/10,000-chunk generated dataset plus the seed fixture).
[Actual store counts](verification/frontend-f6/performance-corpus.json).
Vectors and documents are synthetic; timings are one local observation at each
width, not semantic-quality measurements, load testing or production capacity.

| Width | First page | 50 rows | Next page | Cached previous | 1000-findings render | Filter |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1280 | 565 ms | 366 ms | 473 ms | 117 ms | 4502 ms | 557 ms |
| 390 | 551 ms | 332 ms | 475 ms | 88 ms | 4435 ms | 547 ms |
| 360 | 715 ms | 391 ms | 370 ms | 76 ms | 4437 ms | 549 ms |

At every width the maximum detail concurrency was **3**, and cached previous-page
navigation issued **zero** new detail requests. Filtered search on both backends,
Gap scope lookup and selected-report print preparation also ran; raw observations
are in `verification/frontend-f6/performance-<width>.json`. Search samples are too
small to rank backend performance. Full report rendering at 1000 findings is
visibly expensive (about 4.4–4.5 seconds); that limitation is recorded, with no
virtualization redesign or lost evidence. Filtering and full exports remain usable.

## Remaining SEED work

Frontend feature acceptance gaps are closed or mapped to the existing documented
API needs (full passages, capabilities, typed metadata, global title search/sort,
list chunk counts). SEED platform hardening, verified evaluation and production
packaging remain separate milestones. Existing synthetic labels are unverified;
no quality score is inferred from these UI tests. AWS Compose/Groq/Gemini setup
will be prepared without provisioning or deployment and without requiring Ollama
in production. Root README/deployment docs are completed with packaging.
