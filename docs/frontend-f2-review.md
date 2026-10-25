# F2 review: Ask and Search

Branch: `feat/frontend-f2-ask-search`.

Ask now has an auto-growing question field, Ctrl/Cmd+Enter, regulation filters,
backend/source-count controls, honest citation status, latency/token/request
Details, safe numbered citation buttons and an excerpt drawer. A source list
handles answers without inline markers. Copy includes supplied excerpts; Ask
again, Open as search and the last ten session-only Q&A entries are available.

Search has the same filter/backend/count controls, metadata-rich excerpt cards
and cosine relevance bars. Comparison sends identical parameters to both stores,
keeps independent loading/errors/results, and labels overlap as shared chunk IDs
out of the union of unique results. Stop waiting aborts locally and says the
server may keep working. Document/model/history text is always React text.

The API does not supply full cited chunks, passage positions or model/provider
fields. The drawer labels text **Excerpt**, enriches document metadata using the
existing detail endpoint and keeps excerpts usable on metadata failure. No
optional model/provider chip is fabricated. **Citations checked** explicitly
means membership, with a keyboard-accessible explanation that it does not prove
claim support. No backend endpoint, retrieval or grounding behavior changed.

Validation: **63 unit tests and 17 Playwright tests passed**, zero failures/skips.
Strict no-emit TypeScript, warning-fatal Oxlint (zero warnings), generated-type
freshness and production build passed. Initial `/ask` JS is **101,810 bytes gzip
(101.8 kB)** against the 110,000-byte budget. The browser spec captures every route
and the new research states at 1280/390/360px with overflow assertions.

[Final 80-image index](screenshots/f2/README.md),
[checks](verification/frontend-f2/checks.json),
[bundle measurement](verification/frontend-f2/bundle.json).
The new research layouts and failure states were opened and inspected at desktop
and mobile widths. Visual inspection caught full-page screenshots positioning
sticky/fixed chrome at the previous scroll offset; captures now reset to the top,
and drawers use viewport screenshots. Only this final screenshot set is kept.

The required manual Ask used the native **qwen2.5:3b** profile through Vite on 3100
and API 8001, top_k 2, with the existing real corpus. It returned HTTP 200 in
**12.832 seconds**. Both excerpts concern the Chemical Hygiene Plan and are
relevant to the answer. Page 4 introduces the required-elements list but cuts off
before the SOP/control/equipment/training elements asserted by the answer; those
claims cannot be confirmed from that excerpt alone. Page 5 supports the point
about particularly hazardous substances. Visible support is partial, and this
single manual check is neither a CI criterion nor a verified quality benchmark.
The model supplied no inline markers; the numbered source-list fallback worked.
[Response and manual excerpt assessment](verification/frontend-f2/manual-ask.json),
[manual browser screenshot](screenshots/f2/ask-local-qwen-light-1280.png).

Untested/deferred: full journey and Playwright CI, screen-reader walkthrough,
large-corpus performance (F6), and full cited-chunk lookup (separate API need).
The limited excerpt support is consistent with the existing API limitation;
there is no new API requirement beyond those already recorded in design.md.
