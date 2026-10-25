# F3 review: Agent

Branch: `feat/frontend-f3-agent`.

The Agent now presents partial-run warnings and citation status before the answer,
including empty-answer responses. Time and tool-step limits have plain-language
explanations; raw reasons remain in Details. The answer reuses the safe citation
buttons, membership-only **Citations checked** explanation and labelled excerpt
drawer from Ask. Model/provider chips are omitted because the API has no fields.

The collapsible trace has one timeline entry per tool step, pretty JSON arguments,
summary, latency, tool error and an **Output truncated** badge only when the API's
explicit summary marker is present. Zero completed tool steps are stated. Model,
document, argument and error strings remain text. Requests have elapsed time,
duplicate-submit protection and **Stop waiting**, with the server-work caveat.
Regulation filters and backend selection use the existing generated contract.

The isolated e2e entrypoint now subclasses the existing FakeLLM to choose real
metadata and search tools, then cites IDs actually read from their outputs. It
uses the existing app factory and separate `_test` database/collection. No
production flags, provider/retrieval/grounding changes or new dependencies.
Partial/timeout/truncation/error states are explicitly labelled response fixtures.

Validation: **71 unit tests and 23 Playwright tests passed**, zero failures/skips.
Strict TypeScript, zero-warning Oxlint, generated-type freshness and production
build pass. Initial `/ask` JS is **101,826 bytes gzip (101.8 kB)** against 110 kB.
The extended spec captures every route and research/Agent state at 1280/390/360px
with no horizontal page overflow. Final desktop/mobile Agent screenshots were
opened and inspected. Visual review corrected a nested disclosure-arrow selector;
only the resulting final 100-image set is committed.

[Final screenshots](screenshots/f3/README.md),
[checks](verification/frontend-f3/checks.json),
[bundle](verification/frontend-f3/bundle.json).

No surprising API or behavior issue requires an extra review stop. The accepted
excerpt and truncation-field limitations remain recorded in design.md. Native
Qwen Agent quality was not evaluated in F3; deterministic browser checks use the
fake provider. Full-journey CI, screen-reader and performance work remain F6.
Continue to F4 after green CI and merge; stop there for the planned review.
