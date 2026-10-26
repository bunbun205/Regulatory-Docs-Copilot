# SEED implementation verification — 2026-10-25

## Assessment

The repository has a substantial, tested backend through milestone 6. The merged
revision is `2bdf9ea` (`main`, PR #8). Platform hardening, the frontend, Dockerfiles
and README were uncommitted work at the start of this review. Milestones 7–10
do **not** meet the complete SEED acceptance criteria.

This review checked the implementation against the original project requirements,
ran the available checks against real local services, and recorded results rather
than treating earlier documentation as proof. Git records milestone changes but
does not establish which OpenCode model authored individual lines. No historical
remote CI result was independently checked. Existing work was preserved; limited
local-testing repairs are listed below. No commits or PRs were created.

**Current automated result: 157 tests passed, zero failed/skipped; 87.91% line
coverage of `app/`.** Passing tests do not establish compliance-analysis accuracy:
the verified evaluation datasets and full evaluation harness are missing, and
live local-model requests exposed timeouts.

Evidence is in [verification/2026-10-25/](verification/2026-10-25/).

## What is built in each milestone

| Milestone | Implementation present | Verification and remaining work | Assessment |
| --- | --- | --- | --- |
| **0 — Scaffold** | Python 3.12/uv project and lockfile, Ruff/mypy/pytest configuration, FastAPI health endpoint, Postgres and Qdrant compose services, GitHub Actions skeleton. | Current local Python gates pass after the small formatting repair. Compose configuration validates. Historical remote green CI is not asserted. | Implemented; local checks pass. |
| **1 — Foundation** | SQLAlchemy models and five incremental migrations; SHA-256 API-key storage; read/write scopes; create-key CLI; `/v1/whoami`; error envelope; request IDs and JSON logs. Merged in PR #1. | Auth, 401/403, error and request-ID tests pass. Main DB is at revision `0005`; `alembic check` finds no drift. The later rate-limit middleware bypasses the request-ID contract on its own 429 responses. | Core implemented and tested; hardening regression remains. |
| **2 — Ingestion + ETL** | Pandas manifest validation/rejected rows; PDF/Markdown/text extraction; recursive overlapping chunks with page/section metadata; batched CPU embeddings and NumPy normalization; hash dedupe; document updates; async ingestion jobs and JSON reports. PR #2. | Sample idempotency/update/failure tests pass. Two additional real-corpus ingestion passes each report **0 new, 0 updated, 8 duplicates, 0 failures**. Stores hold 238 chunks/points. Qdrant fan-out remains best effort after Postgres commits; background jobs lack crash recovery. | Implemented and tested, with documented operational limits. |
| **3 — Vector stores** | Shared store Protocol; pgvector cosine/HNSW and Qdrant implementations; metadata/year filters; `/v1/search`; Qdrant reindex and fan-out repair. PRs #3–5. | **5 contract cases per backend, all 10 pass**. Filtered HNSW, score parity, reindex and startup compatibility tests pass. Current 20-question diagnostic gives identical ordered top five results on both stores. | Implemented and tested. |
| **4 — LLM abstraction + RAG** | OpenAI-compatible/Ollama, Anthropic and Azure clients; timeout/retry/error normalization; deterministic scripted FakeLLM; threshold abstention; JSON citation validation; answer usage and retrieval/generation latency. PR #6. | Mocked provider, grounding and abstention tests pass; fake provider is refused in production. Real browser abstention works. A real answerable request initially returned 502 at 60.11 seconds; one CPU-profile rerun returned 200 in 17.61 seconds with a valid citation ID. Semantic support remains unverified. FakeLLM's unscripted default cannot produce the full demo workflow. | Implementation tested; live-model reliability and answer quality are conditional. |
| **5 — Agent** | Framework-free bounded loop; max five tool steps; step/total timeouts; output limits; validated search and Pandas metadata tools; trace, partial-result flags and citation validation. PR #7. | Scripted two-tool, step-limit and timeout tests pass. Live local run returned HTTP 200 after 38.05 seconds, **partial=true, reason=timeout, grounded=false, zero tool steps/citations**. The frontend does not display that warning. | Implemented and tested with test doubles; real run did not complete the intended workflow. |
| **6 — Gap checker** | Clause DataFrame/offsets and boilerplate removal; both analysis directions; deterministic obligation extraction; ephemeral SOP vectors; citation-validated judge/retry/cache; rule-based severity; reports; persisted async jobs, progress/cancellation and per-key active-job uniqueness. PR #8. | Deterministic fixture, injection, citation, job/API and migration tests pass. Five synthetic fixtures produce 39 findings with valid references. A real empty-filtered-corpus job completes correctly. The real clean-SOP diagnostic exceeded its 240-second deadline. Token accounting/caps have reproduced defects; real omission recall is unproven. | Substantial implementation, but important acceptance gaps remain. |
| **7 — Platform hardening** | Uncommitted sliding-window limiter, 429/Retry-After handling, Prometheus counter/histogram middleware and `/metrics`. Existing routes enforce file-size limits and the gap-job uniqueness limit. | Two hardening API tests pass. Reproductions expose missing 429 request IDs/metrics, raw-path metric labels, and a soft token cap. SEED's token-bucket limiter and replaceable RateLimiter Protocol are absent. General request-body limits are absent. | Partial; not ready for sign-off. |
| **8 — Frontend** | Uncommitted Vite/React app; generated API types and openapi-fetch; five feature tabs; upload/polling, search, ask citations, agent trace and pasted-SOP gap report; nginx Dockerfile. | Build, manual type-generation freshness comparison and an additional strict TypeScript invocation pass. Browser listing/search/abstention pass after repairs. Settings/scopes, many controls/states and required frontend tests are missing; details below. | Partial; required browser acceptance flow is not proven. |
| **9 — Evaluation** | A 20-question abstention-score probe; historical corpus comparison docs; synthetic gap-check regression fixtures. | No `eval/run.py`, `eval/metrics.py`, `eval/golden.jsonl`, verified mutation set or `eval/reports/` comparison exists. `python -m eval.run --backend both` fails because the module is absent. All current fixture labels lack human verification. | Not built as specified. |
| **10 — Packaging/docs** | Uncommitted backend/frontend Dockerfiles, four-service compose, README walkthrough; tracked design and earlier verification docs. | Compose syntax passes, but backend CMD exits without running a server. Fresh DB migrations/key bootstrap and container-accessible LLM setup are missing. No Azure deployment plan, architecture diagram/curl walkthrough or final web/Docker/eval CI gates. Fresh-clone compose startup was not validated. | Partial; quickstart is not accepted. |

## Test and check statistics

| Check | Current result | Evidence |
| --- | --- | --- |
| Full backend pytest with real Postgres/Qdrant | **157 passed, 0 failed, 0 skipped; 33.87 s with coverage** | [JUnit](verification/2026-10-25/pytest.xml) |
| API / contract / integration / unit breakdown | **44 / 10 / 17 / 86** | Same JUnit |
| Line coverage, all `app/`, including provider adapters | **3,199 / 3,639 statements = 87.91%**; branch coverage not measured | [Coverage table](verification/2026-10-25/coverage.txt), [JSON](verification/2026-10-25/coverage.json) |
| Areas with lower coverage | CLI **26%**, gap-job worker **63%**, real embedder **66%**, gap API **73%** | Coverage table |
| Ruff lint / format / mypy | Pass; **123 Python files formatted**, **69 source files typechecked** | Initial Ruff failure was one missing blank line in `tests/conftest.py`, repaired before final run. |
| Migrations | `0005 (head)`; no pending ORM changes | `alembic current`, `alembic check` |
| Compose configuration | Pass | `docker compose config -q`; this does not exercise a container startup. |
| Frontend production build | Pass | `npm run build` |
| Frontend additional strict check | Pass | `tsc --strict --noEmit --project tsconfig.app.json`; strict is still absent from committed configuration. |
| Frontend lint | Exit 0, **3 warnings** after repairs, versus 4 initially | `npm run lint` invokes oxlint, not SEED's eslint gate. |
| Generated API types | Current generated file matches regeneration exactly | [Diff](verification/2026-10-25/generated-types.diff), deliberately empty |
| Repository frontend unit/E2E suites | **Absent**; `npm test` fails with missing script | No Vitest/RTL/Playwright dependencies, tests or CI jobs. |
| Additional audit browser check | Real key save/list/search/abstention pass; **0 JS errors, 0 failed requests** | [Browser evidence](verification/2026-10-25/browser-smoke.json), [screenshot](verification/2026-10-25/local-search.png) |

Coverage was installed only under `/tmp/rdc-audit-tools`; Playwright/browser were
installed under `/tmp` as well. Project dependency declarations and lockfiles were
not changed. Backend tests use the guarded `labdocs_test` database and isolated
Qdrant collections. An initial sandbox-blocked attempt was stopped; the statistics
above refer to the completed run with service access.

## Evaluation statistics and their limits

The live inventory was **8 documents / 238 Postgres chunks / 238 Qdrant points**;
Postgres has pgvector **0.8.7**. Both real ingestion reruns left this corpus
unchanged. The installed local generator is `llama3.1:8b`, CPU-only; the example's
default `qwen2.5:7b` is not installed.

### Retrieval diagnostic

The existing probe has ten `in_corpus` and ten `out_of_corpus` group labels, with
no human-verified answer locations. The following counts are diagnostics against
those labels, **not verified retrieval recall or answer correctness**.

| Diagnostic | pgvector | Qdrant |
| --- | ---: | ---: |
| Queries / top_k | 20 / 8 | 20 / 8 |
| In-corpus labels passing threshold 0.75 | 10/10 | 10/10 |
| Out-of-corpus labels below threshold 0.75 | 10/10 | 10/10 |
| In-corpus top-1 min / median / max | 0.771839 / 0.813442 / 0.856611 | Same to six decimals |
| Out-of-corpus top-1 min / median / max | 0.623460 / 0.692466 / 0.719895 | Same to six decimals |
| Warm retrieval p50, including query embedding | **21.56 ms** | **23.13 ms** |
| Warm retrieval p95, including query embedding | **35.06 ms** | **26.51 ms** |

Both stores had **5/5 top-five overlap and identical ordering on 20/20 queries**;
maximum score difference was **2.21e-7**. Latencies use 20 sequential queries per
store, BGE warmed once, pgvector first, Qdrant second, and NumPy percentiles. This
is a small local snapshot, not a load test or evidence one backend is faster.
Raw results: [score probe](verification/2026-10-25/abstention-probe.json) and
[timing/parity diagnostic](verification/2026-10-25/retrieval-diagnostic.json).

### Gap-check diagnostic

The existing regression fixtures use FakeEmbedder and a text-driven
DeterministicFixtureJudge. They validate the scaffolding; their outputs are not
an LLM quality benchmark.

| Existing synthetic fixture | Findings | Valid regulation references | Expected synthetic defect matched |
| --- | ---: | ---: | --- |
| clean_sop | 8 | 8/8 | No defects expected; 0 conflicts/missing/judge failures |
| mutated_conflict | 8 | 8/8 | Yes |
| mutated_missing | 7 | 7/7 | Yes |
| mutated_unsupported | 9 | 9/9 | Yes |
| injection | 7 | 7/7 | Yes; injection clause is not compliant |

Total: **39/39 regulation references and 36/36 SOP references validate**; all four
scripted defect expectations match. **Zero human-verified mutations** enter a
quality denominator. See [fixture results](verification/2026-10-25/deterministic-gapcheck.json).

The separate real-Ollama sweep used the real corpus, top_k 3, relevance threshold
0.60, up to 12 requirements, one concurrent judge, 30-second per-call timeouts and
no provider retries. It recorded **six upstream read timeouts**. The clean fixture
exceeded **240.01 seconds**, producing no completed report; the conflict fixture
was then interrupted and the sweep stopped. There are **zero completed live
fixture reports**, so no real-model recall, false-positive rate, citation-validity
rate or stability score is reported. This diagnostic timeout configuration differs
from the app's initial 60-second default. [Run status](verification/2026-10-25/gapcheck-method.json).

Separately, the real API returned 502 for an answerable RAG request at **60.11 s**,
and a partial, ungrounded agent answer at **38.05 s**. A gap check deliberately
filtered to an empty corpus completed with one `not_covered_by_corpus` finding and
no invented citation. This verifies the job lifecycle and weak-evidence path,
not compliance-judgement quality. [API evidence](verification/2026-10-25/api-smoke.json).

After configuring the CPU testing profile, one answerable RAG rerun returned
**HTTP 200 in 17.61 s**, with **1,133 input / 76 output tokens**, **622.67 ms
retrieval / 16,872.19 ms generation**, and one real cited chunk ID. This was
a changed-profile rerun after model activity, so it does not isolate which
setting or cache/warmup effect improved the result. The answer was marked
`grounded=true`, but the question asks about **closed systems** while its cited
snippet begins **“§ 11.30 Controls for open systems.”** The encryption/signature
claims require human review for scope and support. A valid citation ID alone
does not establish answer correctness.
[CPU-profile response](verification/2026-10-25/cpu-profile-rag.json).

Required SEED quality metrics remain **unavailable**: verified recall@k/MRR,
end-to-end citation quality, verified abstention accuracy, human-reviewed mutation
recall/false positives, and verdict stability by provider. The earlier design doc
also reports a missed authorization omission in a real run; that is a historical
observation, not a new successful result from this audit.

## Issues requiring action

| Priority | Finding and impact | Evidence / recommended change |
| --- | --- | --- |
| **High** | **Docker quickstart cannot serve the API.** The CMD imports `app.main` and exits successfully; it never launches Uvicorn. | [Dockerfile:12](../Dockerfile#L12); reproduced `python -m app.main` exit 0 with no server. Use an ASGI server command, then test a clean stack. |
| **High** | **Fresh-clone startup is incomplete.** No migration/bootstrap stage or key instructions in quickstart; compose fixes production mode and does not wire the LLM settings. Default Ollama address is container loopback. | [Compose](../docker-compose.yml), [README](../README.md). Add migrations, a concrete create-key command, LLM env wiring/optional Ollama service, and startup readiness. Qdrant also has no startup dependency despite required startup probing. |
| **High** | **Gap-check token cap is not hard, and token usage is understated.** Four simultaneous 100-token judgements pass a 100-token budget and consume 400; `caps_hit` stays empty. Two invalid 100-token judge responses are reported as zero tokens. | [Runner:389](../app/gapcheck/runner.py#L389), [judge:189](../app/gapcheck/judge.py#L189), [reproduction](verification/2026-10-25/issue-reproductions.json). Reserve budget before calls; bound prompt/output/retry costs and account for failed calls. |
| **High** | **Verified evaluation is missing.** Passing synthetic checks can mask omission failures and do not satisfy the headline gap-check acceptance. | Missing milestone-9 files; unverified synthetic ground-truth note; historical omission false negative in design.md. Build the harness and obtain author-verified labels before reporting quality scores. |
| **High** | **Live local generation is not yet reliable at the original limits.** Answerable RAG timed out; agent returned no tool trace; full gap fixture did not complete. | API and gap-check evidence above. Measure a CPU-specific profile and structured/tool output before claiming the full browser workflow works. Anthropic/Azure were tested only through mocked HTTP. |
| **High** | **Frontend hides material outcomes.** Search/Agent/Gap errors largely disappear; 401 is not routed to Settings, 429 has no countdown. Agent partial/grounding flags are invisible. Ask now displays API/network errors and request IDs; see the timeout follow-up below. | [Views](../frontend/src/views/); browser mocked a partial response and confirmed no partial-warning text. Add shared error/status handling and view tests. |
| **Medium** | **`grounded=true` verifies citation membership, not semantic support.** The CPU-profile answer to a closed-systems question cites a snippet headed open systems, while the validator reports success. | [Live response](verification/2026-10-25/cpu-profile-rag.json), `app/rag/grounding.py`. This follows the minimal SEED validator design but limits the meaning of the UI/API label; review scope/support in verified evaluations. |
| **Medium** | **429 responses bypass request context and metrics.** Their envelope and headers omit request_id; the Prometheus count misses them. | [Middleware order](../app/main.py#L110), [limiter](../app/core/middleware_ratelimit.py#L31). Reproduced first request 200, second 429, no request-ID header, no recorded 429. Put request context and metrics outside rate limiting and reuse the error envelope. |
| **Medium** | **Limiter differs from SEED and retains arbitrary keys.** Sliding window replaces the required token bucket/Protocol; raw unvalidated header values key an unbounded global dictionary, with no removal of inactive key entries. Most tests bypass limiting via `ENVIRONMENT=testing`. | [Limiter](../app/core/rate_limit.py), [middleware](../app/core/middleware_ratelimit.py). Use a bounded implementation keyed by authenticated identity, a replaceable Protocol, and focused time/refill/eviction tests. |
| **Medium** | **Prometheus endpoint labels use raw paths.** Each document/job UUID or random 404 path creates another counter/histogram series. | [metrics:37](../app/core/metrics.py#L37); two random paths produced two distinct labels. Label by route template and use one label for unmatched routes. |
| **Medium** | **Configured concurrent-gap-job counts above one cannot work.** Settings allow 1–10, but the partial unique DB index allows exactly one active job per key. | [Migration](../app/db/migrations/versions/0005_gapcheck.py), `GAPCHECK_MAX_CONCURRENT_JOBS_PER_KEY`. Restrict the setting to one or implement transactional counting for higher limits. |
| **Medium** | **Resource/readiness gaps remain.** Upload routes enforce file sizes, but there is no general request-size limit; `/readyz` does not load/check BGE. Background ingestion/gap jobs have no crash recovery; interrupted jobs may occupy the active-job slot indefinitely. | `app/main.py`, upload routes and job workers. Add bounded request handling, explicit model readiness and a restart recovery policy. |
| **Medium** | **Required frontend and CI gates are absent.** No repository Vitest/RTL/Playwright suite, fixture-eval gate, Docker builds, generated-type freshness gate or web job. Strict mode is not configured; lint uses oxlint and exits successfully with warnings. | `frontend/package.json`, `tsconfig.app.json`, `.github/workflows/ci.yml`. The temporary audit browser script does not replace the required committed smoke test. |

### Frontend feature acceptance gaps

| View | Present | Still required |
| --- | --- | --- |
| Settings | Header key input; sessionStorage after repair | `/v1/whoami` validation in UI, name/scopes, API URL configuration, scope-aware upload visibility; React Router/settings route. |
| Documents | Upload metadata, list, terminal-status polling | Filters, pagination controls, ingestion report/rejected reasons, visible polling failures, read-only scope behavior. |
| Search | Query and five scored chunks | top_k control, backend selector, metadata/year filters, page display, error/empty states. |
| Ask | Answer and source text; API/network errors with request IDs; pending/duplicate-submit guard | Clickable numbered citation markers, filters/backend, grounded/insufficient badges, tokens and latency breakdown. |
| Agent | Answer, citation labels and trace fields after repair | Collapsible trace, partial/grounding warnings, errors. |
| Gap Check | Pasted text, polling and finding cards | File upload, regulation filters, clause progress, summary counts, finding filters, SOP/regulation comparison and snippets, JSON/Markdown downloads, errors. |

## Local-testing repairs and handoff

Limited repairs made during this review:

- Added Vite `/api` proxying, with `LABDOCS_API_PROXY_TARGET` override.
- Made Save Key update React state immediately and remount the active view when
  the saved key changes; switched browser key storage to sessionStorage and
  labelled the key input.
- Corrected agent display fields from nonexistent `tool_call.*` to the API's
  `tool`, `arguments` and `latency_ms` fields.
- Changed ingestion/gap polling to two seconds; stopped gap polling on cancellation.
- Fixed the conftest formatting failure.
- Added Docker context exclusions for environment files, local dependencies and
  user corpus/uploads. Container builds themselves remain unverified.

The native local testing stack uses **http://127.0.0.1:3100** for the browser and
**http://127.0.0.1:8001/docs** for API exploration. The previous 3000/8000 processes
were preserved during the initial review; the interrupted session's local
processes later stopped and the 3100/8001 stack was restarted.
A write-scoped key named `local-review-20261025` is stored only in
the gitignored `.env.local-testing-key` file (mode 0600), never in this report.
The current CPU testing profile uses `qwen2.5:3b`, two retrieved chunks, a
180-second LLM timeout with no retries, 512-token RAG answers, 60/180-second
agent limits and one concurrent 256-token gap judge. The earlier 8B-profile
RAG check is recorded separately in `cpu-profile-rag.json`.

See [local-testing.md](local-testing.md) for restart commands and manual checks.
Finish the high-priority hardening and frontend gaps, then verified evaluation,
then packaging/CI acceptance before calling the SEED complete.

## Ask timeout follow-up after interruption

The browser's OSHA question reproduced HTTP 502 after **185.34 seconds** with
`llama3.1:8b`, even after reducing retrieval to two chunks. The request reached
FastAPI; the upstream model timed out. See
[8B failure](verification/2026-10-25/ask-fix-llama-failure.json).

The smaller `qwen2.5:3b` download completed and the local stack was restored
using the profile above. Asking the exact same question through the Vite proxy
returned **HTTP 200 in 29.77 seconds**, including **8.19 seconds retrieval**
(first embedding load) and **21.57 seconds generation**. It used **1,322 input /
113 output tokens** and returned two valid chunk IDs from the OSHA laboratory
standard, pages 4 and 5. The bank due-diligence question abstained in **0.048
seconds**, with zero generation tokens. These are smoke checks, not a verified
quality benchmark or proof that the short answer covers every required element.
[Qwen API results](verification/2026-10-25/ask-fix-qwen-api.json).

The real Chromium rerun answered the OSHA question in **4.59 seconds** after
warmup, with the same two citations. All **13 browser assertions passed**:
blank/pending submission guards, duplicate submission making exactly one API
request, answer rendering, citation validation, visible mocked 502/network
errors, retry controls, and no uncaught JavaScript exceptions.
[Browser results](verification/2026-10-25/ask-fix-qwen-browser.json),
[screenshot](verification/2026-10-25/ask-fix-qwen-browser.png).

The concise-answer prompt and Ask UI fixes were preserved. The focused backend
regression rerun passed **23 tests in 2.47 seconds**. Frontend production build,
additional strict TypeScript check, Python lint/format and mypy passed; frontend
lint retained the three previously reported Documents-view warnings. This
follow-up did not rerun the full 157-test coverage suite or evaluate the smaller
model's Agent/Gap Check behavior.
