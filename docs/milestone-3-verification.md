# Milestone 3 condition verification

Date: 2026-10-25

This record covers the five conditions attached to the milestone 3 approval.
All corpus results below came from the real `data/corpus/` PDFs and the real
`BAAI/bge-small-en-v1.5` embedder. `data/sample/` was not used for any number in
this document.

## Environment

- Postgres with pgvector 0.8.7.
- Qdrant 1.20.0.
- Embedding model `BAAI/bge-small-en-v1.5`, 384 dimensions, CPU.
- Separate validation database `labdocs_conditions` and Qdrant collection
  `labdocs_conditions_chunks`; the development database was not modified.

## Real-corpus ingestion

The real manifest contains two OSHA filenames that omit a space present on disk.
The corpus and manifest were left untouched. A temporary copy at
`/tmp/opencode/labdocs-corpus-manifest.csv` corrected only those two filenames
for the full-corpus run.

| Run | Documents ingested | Updates | Duplicates | Rejected rows | Chunks | Qdrant points |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| First full run | 8 | 0 | 0 | 0 | 249 | 249 |
| Second full run | 0 | 0 | 8 | 0 | 0 | 249 |
| Reindex from Postgres | — | — | — | — | 249 | 249 |

The real manifest on its own still reports rows 5 and 6 as `file not found`
because of the missing spaces. Running it against the already-populated
validation database produced 0 new documents, 6 duplicates and 2 rejected rows.

## Ten-query comparison

Ten hand-written queries were embedded once each and sent to both stores with
the same filters and `top_k=5`. The tables below show the top three results for
each backend. Scores are cosine similarity; higher is better.

Document labels:

| Label | Source filename |
| --- | --- |
| `CFR-11` | `21 CFR Part 11 (up to date as of 10-21-2026).pdf` |
| `CFR-58` | `21 CFR Part 58 (up to date as of 10-21-2026).pdf` |
| `CFR-211` | `21 CFR Part 211 (up to date as of 10-21-2026).pdf` |
| `OSHA-1910.1200` | `1910.1200 - Hazard Communication. _ ...pdf` |
| `OSHA-1910.1450` | `1910.1450 - Occupational exposure ...pdf` |
| `DataIntegrity` | `7883441_DataIntegrity.pdf` |
| `Part11-Scope` | `Part-11--Electronic-Records--...-(PDF).pdf` |
| `ProcessValidation` | `Process-Validation--General-Principles-and-Practices.pdf` |

### 1. What are the requirements for electronic records and electronic signatures?

Filter: `source_agency=FDA`

- pgvector top 3: `CFR-11#1` (0.8122); `CFR-11#7` (0.8002); `Part11-Scope#14` (0.7642)
- Qdrant top 3: `CFR-11#1` (0.8122); `CFR-11#7` (0.8002); `Part11-Scope#14` (0.7642)
- top-5 overlap: **5/5** (Jaccard 1.00)

### 2. How should audit trails be reviewed and protected?

Filter: `doc_type=guidance`

- pgvector top 3: `DataIntegrity#22` (0.8168); `Part11-Scope#16` (0.7698); `Part11-Scope#15` (0.7612)
- Qdrant top 3: `DataIntegrity#22` (0.8168); `Part11-Scope#16` (0.7698); `Part11-Scope#15` (0.7612)
- top-5 overlap: **5/5** (Jaccard 1.00)

### 3. What are the responsibilities of the study director in a nonclinical laboratory study?

Filter: `source_agency=FDA, year_min=2026`

- pgvector top 3: `CFR-58#8` (0.8173); `CFR-58#6` (0.7380); `CFR-58#10` (0.7245)
- Qdrant top 3: `CFR-58#8` (0.8173); `CFR-58#6` (0.7380); `CFR-58#10` (0.7245)
- top-5 overlap: **5/5** (Jaccard 1.00)

### 4. Describe process validation stages including installation qualification and continued process verification.

Filter: `year_min=2011`

- pgvector top 3: `ProcessValidation#12` (0.7956); `ProcessValidation#29` (0.7922); `ProcessValidation#13` (0.7717)
- Qdrant top 3: `ProcessValidation#12` (0.7956); `ProcessValidation#29` (0.7922); `ProcessValidation#13` (0.7717)
- top-5 overlap: **5/5** (Jaccard 1.00)

### 5. What are the hazard communication requirements for safety data sheets and labels?

Filter: `source_agency=OSHA`

- pgvector top 3: `OSHA-1910.1200#28` (0.7719); `OSHA-1910.1200#16` (0.7678); `OSHA-1910.1200#19` (0.7613)
- Qdrant top 3: `OSHA-1910.1200#28` (0.7719); `OSHA-1910.1200#16` (0.7678); `OSHA-1910.1200#19` (0.7613)
- top-5 overlap: **5/5** (Jaccard 1.00)

### 6. What are the requirements for employee exposure monitoring in laboratories?

Filter: `source_agency=OSHA`

- pgvector top 3: `OSHA-1910.1450#6` (0.8044); `OSHA-1910.1450#11` (0.8033); `OSHA-1910.1450#14` (0.7910)
- Qdrant top 3: `OSHA-1910.1450#6` (0.8044); `OSHA-1910.1450#11` (0.8033); `OSHA-1910.1450#14` (0.7910)
- top-5 overlap: **5/5** (Jaccard 1.00)

### 7. How should batch production and control records be prepared and reviewed?

Filter: `doc_type=regulation`

- pgvector top 3: `CFR-211#47` (0.8087); `CFR-211#44` (0.7449); `CFR-211#23` (0.7358)
- Qdrant top 3: `CFR-211#47` (0.8087); `CFR-211#44` (0.7449); `CFR-211#23` (0.7358)
- top-5 overlap: **5/5** (Jaccard 1.00)

### 8. What are the requirements for computerized system validation and data integrity?

Filter: `source_agency=FDA`

- pgvector top 3: `Part11-Scope#14` (0.7382); `ProcessValidation#29` (0.7331); `CFR-211#14` (0.7264)
- Qdrant top 3: `Part11-Scope#14` (0.7382); `ProcessValidation#29` (0.7331); `CFR-211#14` (0.7264)
- top-5 overlap: **5/5** (Jaccard 1.00)

### 9. What training and personnel qualification records are required?

Filter: `source_agency=FDA, year_max=2018`

- pgvector top 3: `ProcessValidation#30` (0.6768); `DataIntegrity#13` (0.6608); `ProcessValidation#32` (0.6576)
- Qdrant top 3: `ProcessValidation#30` (0.6768); `DataIntegrity#13` (0.6608); `ProcessValidation#32` (0.6576)
- top-5 overlap: **5/5** (Jaccard 1.00)

### 10. How should corrective and preventive actions be documented and verified?

Filter: `source_agency=FDA`

- pgvector top 3: `CFR-58#9` (0.7431); `ProcessValidation#29` (0.7061); `ProcessValidation#3` (0.6872)
- Qdrant top 3: `CFR-58#9` (0.7431); `ProcessValidation#29` (0.7061); `ProcessValidation#3` (0.6872)
- top-5 overlap: **5/5** (Jaccard 1.00)

### Disagreement check

There were no top-5 disagreements: all ten queries had 5/5 overlap. The 50
shared top-5 chunks had a maximum absolute score difference of
`1.0e-6` and a mean difference of `1.6e-7`. Rebuilding Qdrant with
`reindex --backend qdrant` produced the same top-5 sets for all ten queries.

Both stores use cosine similarity on L2-normalized embeddings:
`PgVectorStore` returns `1 - cosine_distance`, and Qdrant uses a
`Distance.COSINE` collection. Scores are therefore on the same scale and
higher is better.

## Filtered HNSW regression

A selective-filter reproduction used 500 synthetic documents with 5 chunks each
(2,500 chunks). Five chunks belonged to a `Rare Agency` document whose vectors
were orthogonal to the query; the other 2,495 chunks dominated the nearest
neighbor candidate set. `enable_seqscan=off` forced the HNSW index and the
filter matched only the five rare chunks.

| Code path | Matching chunks | Returned with `top_k=50` |
| --- | ---: | ---: |
| Before fix | 5 | 0 |
| After iterative scan + exact fallback | 5 | 5 |

Decision: filtered pgvector searches set
`hnsw.iterative_scan = 'relaxed_order'`. If the approximate result returns fewer
rows than `top_k` and the exact matching count is larger than the returned row
count, the store retries with sequential scan forced (`enable_seqscan=on`,
`enable_indexscan=off`, `enable_indexonlyscan=off`,
`enable_bitmapscan=off`). This prioritizes correctness for selective filters;
the fallback only runs on observed under-return. The regression test uses the
same 2,500-chunk shape and asserts all five rare chunks are returned.

## Update semantics

- Identity is `(source_agency, filename)`; migration `0004` adds
  `uq_documents_agency_filename`.
- A document whose raw-byte SHA-256 already exists is a duplicate, regardless
  of filename or metadata. Re-ingesting a duplicate also replaces that
  document's external points so a missing Qdrant index is repaired.
- Same identity with a new SHA-256 is an update. The pipeline locks the document
  row, updates metadata, deletes all old chunks and inserts the new chunks in a
  single Postgres transaction. After commit it deletes the document's Qdrant
  points and inserts the new points.
- A shorter replacement document was tested: the old chunk IDs disappear, the
  chunk count drops, and the new text is the only text stored. A metadata-only
  change is reported as a duplicate and keeps the original metadata.
- If the external replace fails, Postgres keeps the new content and the job
  fails safely. Re-ingesting the same new content takes the duplicate path and
  repairs Qdrant.

## Other condition checks

- `reindex --backend qdrant` rebuilt 8 documents / 249 chunks from Postgres and
  left 249 Qdrant points. It is a delete-and-recreate operation, not an atomic
  cross-store transaction.
- A Qdrant fan-out failure injection left the Postgres document committed, the
  job failed with a safe error that did not contain the injected exception text,
  and a duplicate re-ingest repaired the Qdrant points.
- Startup validates the configured embedder dimension, the Qdrant collection
  dimension and the Qdrant distance metric. A mismatch raises a startup error.
- `top_k` is capped at 50 in both API schemas and store implementations.
  Unknown search/filter fields return HTTP 422.
- A real-lifespan test starts `create_app()` with Postgres, the fake embedder
  and Qdrant, uploads a document through the API, and retrieves it through the
  Qdrant backend.
