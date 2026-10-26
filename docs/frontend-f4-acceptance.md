# F4 final acceptance — 2026-10-26

Reviewed against the original Gap Check, security, test and frontend criteria,
plus [F4 review](frontend-f4-review.md). The user's conditional approval
permits merging PR #14 after these checks and green CI. F5 remains a separate PR.

| Criterion | Evidence and result |
| --- | --- |
| Input and scope | Paste and real Markdown upload, local type/empty/size checks, existing API filters and default limits. Scope uses document count, not a coverage promise. Authoritative 422 cap failures stay visible. |
| Cancellation | Unit and real-browser jobs distinguish a cancel request from terminal cancellation. Polling continues until confirmation; cancelled runs do not show a misleading extraction error. |
| Resume and poll failure | Bookmarked/reloaded job routes resume polling with server timestamps. Poll errors retain last confirmed progress and expose retry/error details. Terminal jobs stop polling. |
| Partial failures | All eight verdicts exercised. judge_failed remains unresolved with manual-review count/banner; outside-corpus findings remain neutral. Caps warn that analysis may be incomplete. Failed jobs and completed jobs missing reports have explicit states. |
| Report completeness | Severity/direction/verdict/text filters, URL restoration, severity/clause ordering, all supplied findings and comparisons. Unknown optional metadata is narrowed without invented values. Excerpts are labelled as excerpts. |
| Untrusted content | SOP, regulation, rationale, suggestion, metadata and titles use React text nodes, never HTML parsing. Hostile img/script and Markdown links have regression coverage. Markdown escapes HTML and formatting; JSON is a downloaded data blob, never embedded as executable script. Printed hostile SOP tags remain visible text. |
| JSON export | Browser download deep-equals the complete API report even while the screen is filtered. It preserves original clauses, findings, provenance, metadata, caps and disclaimer. |
| Markdown export | Browser checks every finding's rationale/suggestion, every citation snippet/ID, every SOP clause and the disclaimer. Acceptance review added requirement ID/strength, document/chunk IDs, retrieval scores labelled as not confidence, input/output tokens, configured caps, incomplete/manual-review caveats and an appendix of all supplied SOP clauses, including unlinked clauses. |
| Print/PDF | Current selection is explicitly stated. beforeprint opens every selected comparison, including newly mounted cards, and afterprint restores disclosure state. All-eight fixture PDF asserts eight rationales and eight suggestions; source IDs, page, excerpt, SOP section/text, requirement strength and disclaimer remain visible. Download exports remain full-report regardless of print filters. |

Validation: **93 unit tests, 32 full-suite browser tests, 3 final export/print
browser repeats, and 155 committed backend tests passed**, zero failures/skips.
Strict TypeScript, warning-fatal lint (zero warnings), generated-type freshness
from the clean app factory, production build and bundle budget pass. Initial
Ask JS: **102,094 bytes gzip**. The backend run used a clean worktree so unfinished
platform changes and the two separately documented platform tests were excluded.
No tests or lint rules were weakened. No production backend or dependency changes.

Screenshots at 1280/390/360px assert no horizontal page overflow. Final desktop
and mobile report captures and the rendered print PDF were opened and inspected.
Recorded fake/native runs and their model-quality limitations remain in the F4
review; acceptance did not reinterpret them as verified regulatory conclusions.

## Explicit F6 follow-ups

- Drive **PDF and TXT uploads end to end in the browser** (upload, poll, report,
  comparison, export), using the isolated fake-provider stack. Markdown is already
  driven end to end; extension validation/backend extraction do not replace these
  two browser journeys.
- Complete **accessibility verification**: keyboard-only full journey, drawer
  focus/return and Escape, screen-reader announcements/landmarks, contrast and
  reduced-motion checks. Existing semantic/control tests are not a full audit.
- Measure **large-corpus performance**: document pagination/chunk-count fan-out,
  scope lookup, long reports/filtering/printing and request timing with a realistic
  corpus. The small deterministic fixture is not performance evidence at scale.
- Finish the combined upload → Search → Ask/citation → Agent → Gap/filter/export
  journey and run Playwright in CI with the fake provider only.
