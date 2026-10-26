# Evaluation and author review

The runner exercises the application's retriever, answerer and gap-check runner.
It writes timestamped JSON and Markdown under `eval/reports/`. A run is evidence
of what was measured, not a regulatory compliance determination.

**Current status:** `golden.jsonl` contains 30 agent-drafted candidates from the
eight supplied PDFs: 20 single-source, five multi-document and five candidate
unanswerables. Every row is `verified: false`. No human-authored clean SOPs or
reviewed mutations have been supplied; `mutations.jsonl` is intentionally empty.
Milestone 9's verified-data acceptance remains pending. The synthetic CI fixture
does not satisfy that acceptance criterion.

## Commands

Run from the repository root after installing locked dependencies and ingesting
the author's corpus into both stores. The usual `LABDOCS_*` settings apply.

```sh
# CI regression: deterministic synthetic corpus, NumPy store and scripted model.
uv run python -m eval.run --fixture

# Real stores, unreviewed queries: retrieval timings/IDs only; no model calls.
uv run python -m eval.run --backend both --retrieval-only --diagnostic-unverified

# After author review: scored retrieval, generation and repeated gap checks.
uv run python -m eval.run --backend both
```

Exit status is `0` for a completed run with reviewed inputs (or the explicit CI
fixture), `1` for execution failures, and `2` for a report awaiting human input.
Status `reviewed_inputs` only describes label eligibility; it does not certify
the quality of the measured results or completion of all milestone requirements.
Initialization errors such as an empty or mismatched corpus abort without a
report. Diagnostic errors also fail the command. Reports use `null`/`unavailable`
when a denominator is empty, never an invented zero or perfect score.

Run each provider/model separately with `LABDOCS_LLM_PROVIDER`,
`LABDOCS_LLM_BASE_URL`, `LABDOCS_LLM_MODEL` and `LABDOCS_LLM_API_KEY`. Reports record
the provider and model, never the API key. A scored run makes bounded model calls
for eligible rows; `--retrieval-only` disables all generation and gap analysis.
Generation is never enabled for unverified question diagnostics.

## Review the question candidates

1. Open the exact PDF named in each `expected_sources` entry. `page` means the
   **one-based PDF page**, which can differ from the printed document page.
2. Confirm the question is well posed and the cited page/section actually
   supports it. Correct candidate locations and quotes as needed. A short quote
   identifies a retrieval target; it is not a complete expected answer.
   Multi-document questions require support in at least two distinct documents.
3. For unanswerables, inspect the entire supplied corpus. The absence of an
   answer is relative to that corpus, not to the model's outside knowledge.
4. Only the author sets `verified: true`, with `reviewed_by` and a date such as
   `reviewed_at: "2026-10-26"`. Leave all other rows false. Re-review after changes
   to a question, target, source document, corpus, or SOP. The runner checks
   file hashes, source locations/quotes and the reviewed corpus snapshot.

The Pydantic schemas in `datasets.py` are authoritative. Unknown fields,
duplicate IDs, string booleans and incomplete review records are rejected.
Review declarations are an author assertion, not a cryptographic signature.
The corpus snapshot is SHA-256 over JSON of sorted unique `(filename,
content_sha256)` pairs loaded from Postgres. Copy the snapshot from an actual
report; do not substitute a different corpus to make a label pass.

## Supply clean SOPs and mutations

The author supplies their own SOPs or identifies public templates and verifies
their suitability as clean baselines against the selected corpus. The agent
must not invent a baseline and call it human ground truth. Private SOP files and
raw reports belong in ignored `eval/review/` or another private directory.

Add one JSON object per line to `mutations.jsonl`, using these fields:

| Field | Meaning |
|---|---|
| `id`, `kind` | Stable unique ID; `clean` or `mutation` |
| `sop_path` | Path relative to the dataset file, or an absolute local path |
| `sop_sha256` | SHA-256 of the exact SOP file bytes |
| `provenance` | Author/source and permission to use the SOP |
| `corpus_snapshot` | Snapshot of the corpus the author reviewed |
| `verified`, `reviewed_by`, `reviewed_at` | Same review rules as questions |
| `filters` | Optional application's search filters (agency, type, year bounds) |
| `baseline_id` | For mutations, ID of a verified clean baseline in this dataset |
| `defects` | For mutations, one or more author-reviewed expected defects |

A defect contains `id`, `description`, `direction`, accepted `verdicts` and a
`source` with the same filename/hash/page-or-section/quote schema as questions.
For `sop_to_regulation`, supply `sop_quote` identifying the affected clause and
accept `conflict` or `partial`. For `regulation_to_sop`, supply a short
`requirement_quote` expected within the finding's regulation citation snippet
(at most 300 characters); accept `missing` or `partially_addressed`. Matching
another obligation from the same chunk is insufficient. Verify injected
deletions, contradictions and unsupported practices before marking a mutation
eligible. An unsupported practice cannot count as a correctly cited violation
unless the corpus actually supports that judgment.

Clean baseline eligibility and finding-level false-positive review are separate.
After a run, inspect each complete local `eval/review/<report-sha256>.json`.
Add an object to `clean_reviews.json` with `report_sha256`, `reviewed_by`,
`reviewed_at`, `false_positive_ids` (all wrongly flagged defect finding IDs),
and optional `notes`. An empty list is an explicit review of that exact report;
absence of a review means unknown, not zero false positives.

```sh
uv run python -m eval.run --rescore-report eval/reports/<timestamp>.json
```

This rescores those saved reports without calling a model again. Hashes include
the exact run and model metadata; a review never transfers to a fresh rerun.
Do not commit private source text, raw reports or provider credentials. Public
reports contain sample IDs, counts and report hashes, not SOP contents.

## Metric definitions and limits

- **Recall@k:** fraction of expected source targets retrieved per verified
  answerable question, macro-averaged across questions. Matching requires
  filename, SHA-256, page/section and normalized quote. Multiple matching chunks
  do not count a target twice. **MRR:** reciprocal rank of the first relevant
  hit, then macro-average; multi-source recall remains a separate measure.
- **Raw citation validity:** valid retrieved IDs / all proposed citation entries,
  measured before the application strips invalid IDs. Malformed/no-citation
  responses supply no proposed entries; the separate `citation_valid_answer_rate`
  includes every eligible generated answerable question and exposes failures or
  missing citations. Neither metric establishes semantic answer correctness.
- **Abstention accuracy:** application `insufficient_evidence` decisions / all
  verified unanswerables with generation enabled. Failed runs count as misses.
  This measures the application's evidence-threshold abstention behavior, not
  a subjective reading of a model's refusal prose.
- **Latency:** NumPy p50/p95 in milliseconds, with sample counts. Retrieval
  includes query embedding and store search. The embedder is warmed once;
  backend order is sequential. Total latency includes generation and failures.
  Diagnostic timings and hit-set agreement use unreviewed questions only as
  workloads and never become quality scores.
- **Injected-defect recall:** correctly detected labeled defects / expected
  defects across all repeats. Matching requires the expected direction, verdict,
  affected clause or requirement, and correct regulation citation. Failed runs
  retain their expected defects in the denominator. Multiple findings cannot
  count a single labeled defect twice.
- **Gap citation validity:** valid regulation and SOP references / emitted
  references. Regulation IDs, document, page and quoted snippet must match the
  corpus; SOP IDs must exist in the report. An empty reference set is unavailable.
  `judge_failed`, caps and run errors are reported separately; valid citations
  do not imply a successful or complete judgment.
- **Clean false-positive rate:** author-marked erroneous defect findings /
  all determinate findings in exact reviewed clean reports. Determinate means
  `compliant`, `addressed`, `partial`, `conflict`, `partially_addressed`, or
  `missing`; unknown coverage and judge failures are excluded. This is a
  finding-level rate, not a specificity estimate over every possible obligation.
- **Stability:** mean pairwise Jaccard of direction/verdict/SOP-reference/source
  signatures over successful report pairs with a nonempty union. Generated
  finding/requirement numbering does not affect it. Fresh judges disable the
  persistent cache on every repeat. Stable failures can still score highly;
  read judge-failure counts, caps and recall alongside stability.

The real runner requires equal store counts and checks retrieved text/document
identities against Postgres. This detects observed stale records, not every
possible unqueried mismatch. Full raw gap evidence remains local for review.
