# Milestone 3 verification

Date: 2026-10-25

This record covers the five follow-up conditions attached to the milestone 3
approval. All corpus results below came from the real `data/corpus/` PDFs, the
real `data/corpus/manifest.csv` and the real `BAAI/bge-small-en-v1.5` embedder.
`data/sample/` was not used for any number in this document. The validation
database and collection from the earlier condition run were deleted.

## Environment

- Postgres with pgvector **0.8.7**, pinned as `pgvector/pgvector:0.8.7-pg16` in
  `docker-compose.yml` and CI. Startup and the ingest/reindex CLI reject a
  database whose pgvector extension is older than 0.8.0, the first version with
  `hnsw.iterative_scan`.
- Qdrant **1.20.0**, pinned as `qdrant/qdrant:v1.20.0`.
- Embedding model `BAAI/bge-small-en-v1.5`, 384 dimensions, CPU.
- Main database `labdocs` at migration `0004`; main Qdrant collection
  `labdocs_chunks`.
- The validation database `labdocs_conditions` and collection
  `labdocs_conditions_chunks` were dropped before this run.

## Real-corpus ingestion

The real manifest has no missing files: all eight rows are valid. The corpus was
ingested twice into the main database and Qdrant with `VECTOR_BACKEND=both`.

| Run | Documents ingested | Updates | Metadata updates | Duplicates | Rejected rows | Chunks | Qdrant points |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| First run | 8 | 0 | 0 | 0 | 0 | 238 | 238 |
| Second run | 0 | 0 | 0 | 8 | 0 | 0 | 238 |

The second run performed no embedding calls and left the document/chunk counts
unchanged. Per-document chunk counts after boilerplate stripping:

| Document | Pages | Chunks |
| --- | ---: | ---: |
| `21 CFR Part 11 (up to date as of 10-21-2026).pdf` | 6 | 11 |
| `21 CFR Part 211 (up to date as of 10-21-2026).pdf` | 29 | 50 |
| `21 CFR Part 58 (up to date as of 10-21-2026).pdf` | 19 | 33 |
| `7883441_DataIntegrity.pdf` | 17 | 33 |
| `osha-1910-1200-hazard-communication.pdf` | 20 | 40 |
| `osha-1910-1450-lab-standard.pdf` | 8 | 14 |
| `Part-11--Electronic-Records--Electronic-Signatures---Scope-and-Application-(PDF).pdf` | 12 | 20 |
| `Process-Validation--General-Principles-and-Practices.pdf` | 22 | 37 |

## Boilerplate stripping and chunk audit

The PDF extractor now strips cross-page print furniture before chunking. It
combines explicit patterns for eCFR/OSHA/FDA output with a frequency rule for
short lines repeated on at least 60% of pages (minimum three pages). Covered
furniture includes browser print date/title headers, standalone URLs and
page-number footers, eCFR "up to date as of" banners, eCFR running
headers/footers, the FDA "Contains Nonbinding Recommendations" header, and the
OSHA navigation/footer block. Unit tests cover repeated headers with changing
page numbers, URL footers, navigation text and preservation of body text.

The extraction change reduced the corpus from 249 to 238 chunks. The full
per-document token-length distribution and three reproducible random chunk texts
per document are in
[`docs/milestone-3-corpus-audit.md`](milestone-3-corpus-audit.md).

## Ten-query comparison

Ten hand-written queries were embedded once each and sent to both stores with
the same filters and `top_k=5`. Each result below includes the query text, the
first 200 characters of each top-three chunk, and the top-five overlap. Scores
are cosine similarity; higher is better.

Document labels:

| Label | Source filename |
| --- | --- |
| `CFR-11` | `21 CFR Part 11 (up to date as of 10-21-2026).pdf` |
| `CFR-58` | `21 CFR Part 58 (up to date as of 10-21-2026).pdf` |
| `CFR-211` | `21 CFR Part 211 (up to date as of 10-21-2026).pdf` |
| `OSHA-1910.1200` | `osha-1910-1200-hazard-communication.pdf` |
| `OSHA-1910.1450` | `osha-1910-1450-lab-standard.pdf` |
| `DataIntegrity` | `7883441_DataIntegrity.pdf` |
| `Part11-Scope` | `Part-11--Electronic-Records--Electronic-Signatures---Scope-and-Application-(PDF).pdf` |
| `ProcessValidation` | `Process-Validation--General-Principles-and-Practices.pdf` |

### 1. What are the requirements for electronic records and electronic signatures?

Filter: `source_agency=FDA`

- pgvector top 3:
  - `CFR-11#1` (0.8122): "[62 FR 13464, Mar. 20, 1997, as amended at 69 FR 71655, Dec. 9, 2004; 79 FR 71253, 71291, Dec. 1, 2014; 80 FR 56144, 56336, Sept. 17, 2015; 80 FR 74352, 74547, 74667, Nov. 27, 2015; 81 FR 20170, Apr. "
  - `CFR-11#7` (0.8002): "§ 11.30 Controls for open systems. Persons who use open systems to create, modify, maintain, or transmit electronic records shall employ procedures and controls designed to ensure the authenticity, in"
  - `Part11-Scope#14` (0.7635): "in generating a submission, is not a part 11 record unless it is otherwise required to be 204 maintained under a predicate rule and it is maintained in electronic format. 205 • Electronic signatures t"
- Qdrant top 3:
  - `CFR-11#1` (0.8122): "[62 FR 13464, Mar. 20, 1997, as amended at 69 FR 71655, Dec. 9, 2004; 79 FR 71253, 71291, Dec. 1, 2014; 80 FR 56144, 56336, Sept. 17, 2015; 80 FR 74352, 74547, 74667, Nov. 27, 2015; 81 FR 20170, Apr. "
  - `CFR-11#7` (0.8002): "§ 11.30 Controls for open systems. Persons who use open systems to create, modify, maintain, or transmit electronic records shall employ procedures and controls designed to ensure the authenticity, in"
  - `Part11-Scope#14` (0.7635): "in generating a submission, is not a part 11 record unless it is otherwise required to be 204 maintained under a predicate rule and it is maintained in electronic format. 205 • Electronic signatures t"
- top-5 overlap: **5/5**

### 2. How should audit trails be reviewed and protected?

Filter: `doc_type=guidance`

- pgvector top 3:
  - `DataIntegrity#22` (0.8098): "212.70(f)(1)(vi)). All data required to recreate a CGMP activity should be maintained as part of the complete record. 7. Who should review audit trails? Audit trail review is similar to assessing cros"
  - `Part11-Scope#16` (0.7629): "reliability of the records.6 We recommend that you base your decision on whether to apply audit 250 trails, or other appropriate measures, on the need to comply with predicate rule requirements, a 251"
  - `DataIntegrity#23` (0.7571): "See the audit trail definition in 1.c. above for further information on audit trails. 9. Can electronic copies be used as accurate reproductions of paper or electronic records? Yes. Electronic copies "
- Qdrant top 3:
  - `DataIntegrity#22` (0.8098): "212.70(f)(1)(vi)). All data required to recreate a CGMP activity should be maintained as part of the complete record. 7. Who should review audit trails? Audit trail review is similar to assessing cros"
  - `Part11-Scope#16` (0.7629): "reliability of the records.6 We recommend that you base your decision on whether to apply audit 250 trails, or other appropriate measures, on the need to comply with predicate rule requirements, a 251"
  - `DataIntegrity#23` (0.7571): "See the audit trail definition in 1.c. above for further information on audit trails. 9. Can electronic copies be used as accurate reproductions of paper or electronic records? Yes. Electronic copies "
- top-5 overlap: **5/5**

### 3. What are the responsibilities of the study director in a nonclinical laboratory study?

Filter: `source_agency=FDA, year_min=2026`

- pgvector top 3:
  - `CFR-58#8` (0.8173): "§ 58.31 Testing facility management. For each nonclinical laboratory study, testing facility management shall: [43 FR 60013, Dec. 22, 1978, as amended at 52 FR 33780, Sept. 4, 1987] § 58.33 Study dire"
  - `CFR-58#6` (0.7380): "[43 FR 60013, Dec. 22, 1978, as amended at 52 FR 33779, Sept. 4, 1987; 54 FR 9039, Mar. 3, 1989; 64 FR 56448, Oct. 20, 1999; 67 FR 35729, May 21, 2002] § 58.10 Applicability to studies performed under"
  - `CFR-58#10` (0.7245): "[43 FR 60013, Dec. 22, 1978; 44 FR 17657, Mar. 23, 1979] § 58.35 Quality assurance unit. (d) Test systems are as specified in the protocol. (e) All applicable good laboratory practice regulations are "
- Qdrant top 3:
  - `CFR-58#8` (0.8173): "§ 58.31 Testing facility management. For each nonclinical laboratory study, testing facility management shall: [43 FR 60013, Dec. 22, 1978, as amended at 52 FR 33780, Sept. 4, 1987] § 58.33 Study dire"
  - `CFR-58#6` (0.7380): "[43 FR 60013, Dec. 22, 1978, as amended at 52 FR 33779, Sept. 4, 1987; 54 FR 9039, Mar. 3, 1989; 64 FR 56448, Oct. 20, 1999; 67 FR 35729, May 21, 2002] § 58.10 Applicability to studies performed under"
  - `CFR-58#10` (0.7245): "[43 FR 60013, Dec. 22, 1978; 44 FR 17657, Mar. 23, 1979] § 58.35 Quality assurance unit. (d) Test systems are as specified in the protocol. (e) All applicable good laboratory practice regulations are "
- top-5 overlap: **5/5**

### 4. Describe process validation stages including installation qualification and continued process verification.

Filter: `year_min=2011`

- pgvector top 3:
  - `ProcessValidation#27` (0.8008): "• Evaluate any unexpected observations and additional data not specified in the protocol. • Summarize and discuss all manufacturing nonconformances such as deviations, aberrant test results, or other "
  - `ProcessValidation#12` (0.7966): "• Each step of a manufacturing process is controlled to assure that the finished product meets all quality attributes including specifications. B. Approach to Process Validation For purposes of this g"
  - `ProcessValidation#13` (0.7695): "product. Focusing exclusively on qualification efforts without also understanding the manufacturing process and associated variations may not lead to adequate assurance of quality. After establishing "
- Qdrant top 3:
  - `ProcessValidation#27` (0.8008): "• Evaluate any unexpected observations and additional data not specified in the protocol. • Summarize and discuss all manufacturing nonconformances such as deviations, aberrant test results, or other "
  - `ProcessValidation#12` (0.7966): "• Each step of a manufacturing process is controlled to assure that the finished product meets all quality attributes including specifications. B. Approach to Process Validation For purposes of this g"
  - `ProcessValidation#13` (0.7695): "product. Focusing exclusively on qualification efforts without also understanding the manufacturing process and associated variations may not lead to adequate assurance of quality. After establishing "
- top-5 overlap: **5/5**

### 5. What are the hazard communication requirements for safety data sheets and labels?

Filter: `source_agency=OSHA`

- pgvector top 3:
  - `OSHA-1910.1200#28` (0.7719): "Employers shall provide employees with effective information and training on hazardous chemicals in their work area at the time of their initial assignment, and whenever a new chemical hazard the empl"
  - `OSHA-1910.1200#16` (0.7678): "The methods the employer will use to inform the other employer(s) of any precautionary measures that need to be taken to protect employees during the workplace's normal operating conditions and in for"
  - `OSHA-1910.1200#0` (0.7674): "Part Number: 1910 Part Number Title: Occupational Safety and Health Standards Standard Number: 1910.1200 Title: Hazard Communication. Appendix: A, B, C, D, E, F GPO Source: e-CFR 1910.1200(a) Purpose."
- Qdrant top 3:
  - `OSHA-1910.1200#28` (0.7719): "Employers shall provide employees with effective information and training on hazardous chemicals in their work area at the time of their initial assignment, and whenever a new chemical hazard the empl"
  - `OSHA-1910.1200#16` (0.7678): "The methods the employer will use to inform the other employer(s) of any precautionary measures that need to be taken to protect employees during the workplace's normal operating conditions and in for"
  - `OSHA-1910.1200#0` (0.7674): "Part Number: 1910 Part Number Title: Occupational Safety and Health Standards Standard Number: 1910.1200 Title: Hazard Communication. Appendix: A, B, C, D, E, F GPO Source: e-CFR 1910.1200(a) Purpose."
- top-5 overlap: **5/5**

### 6. What are the requirements for employee exposure monitoring in laboratories?

Filter: `source_agency=OSHA`

- pgvector top 3:
  - `OSHA-1910.1450#9` (0.8033): "Methods and observations that may be used to detect the presence or release of a hazardous chemical (such as monitoring conducted by the employer, continuous monitoring devices, visual appearance or o"
  - `OSHA-1910.1450#12` (0.7873): "1910.1450(h)(2)(iii) If the chemical substance is produced for another user outside of the laboratory, the employer shall comply with the Hazard Communication Standard (29 CFR 1910.1200) including the"
  - `OSHA-1910.1200#33` (0.7796): "The chemical manufacturer, importer, or employer may require a written statement of need and confidentiality agreement, in accordance with the provisions of paragraphs (i)(3) and (4) of this section, "
- Qdrant top 3:
  - `OSHA-1910.1450#9` (0.8033): "Methods and observations that may be used to detect the presence or release of a hazardous chemical (such as monitoring conducted by the employer, continuous monitoring devices, visual appearance or o"
  - `OSHA-1910.1450#12` (0.7873): "1910.1450(h)(2)(iii) If the chemical substance is produced for another user outside of the laboratory, the employer shall comply with the Hazard Communication Standard (29 CFR 1910.1200) including the"
  - `OSHA-1910.1200#33` (0.7796): "The chemical manufacturer, importer, or employer may require a written statement of need and confidentiality agreement, in accordance with the provisions of paragraphs (i)(3) and (4) of this section, "
- top-5 overlap: **5/5**

### 7. How should batch production and control records be prepared and reviewed?

Filter: `doc_type=regulation`

- pgvector top 3:
  - `CFR-211#44` (0.8087): "§ 211.188 Batch production and control records. Batch production and control records shall be prepared for each batch of drug product produced and shall include complete information relating to the pr"
  - `CFR-211#41` (0.7513): "Written procedures shall be established and followed for such evaluations and shall include provisions for: (1) A review of a representative number of batches, whether approved or rejected, and, where"
  - `CFR-211#20` (0.7358): "§ 211.105 Equipment identification. § 211.110 Sampling and testing of in-process materials and drug products. [43 FR 45077, Sept. 29, 1978, as amended at 73 FR 51932, Sept. 8, 2008] § 211.111 Time lim"
- Qdrant top 3:
  - `CFR-211#44` (0.8087): "§ 211.188 Batch production and control records. Batch production and control records shall be prepared for each batch of drug product produced and shall include complete information relating to the pr"
  - `CFR-211#41` (0.7513): "Written procedures shall be established and followed for such evaluations and shall include provisions for: (1) A review of a representative number of batches, whether approved or rejected, and, where"
  - `CFR-211#20` (0.7358): "§ 211.105 Equipment identification. § 211.110 Sampling and testing of in-process materials and drug products. [43 FR 45077, Sept. 29, 1978, as amended at 73 FR 51932, Sept. 8, 2008] § 211.111 Time lim"
- top-5 overlap: **5/5**

### 8. What are the requirements for computerized system validation and data integrity?

Filter: `source_agency=FDA`

- pgvector top 3:
  - `CFR-211#12` (0.7431): "A backup file of data entered into the computer or related system shall be maintained except where certain data, such as calculations performed in connection with laboratory analysis, are eliminated b"
  - `Part11-Scope#14` (0.7336): "in generating a submission, is not a part 11 record unless it is otherwise required to be 204 maintained under a predicate rule and it is maintained in electronic format. 205 • Electronic signatures t"
  - `ProcessValidation#27` (0.7280): "• Evaluate any unexpected observations and additional data not specified in the protocol. • Summarize and discuss all manufacturing nonconformances such as deviations, aberrant test results, or other "
- Qdrant top 3:
  - `CFR-211#12` (0.7431): "A backup file of data entered into the computer or related system shall be maintained except where certain data, such as calculations performed in connection with laboratory analysis, are eliminated b"
  - `Part11-Scope#14` (0.7336): "in generating a submission, is not a part 11 record unless it is otherwise required to be 204 maintained under a predicate rule and it is maintained in electronic format. 205 • Electronic signatures t"
  - `ProcessValidation#27` (0.7280): "• Evaluate any unexpected observations and additional data not specified in the protocol. • Summarize and discuss all manufacturing nonconformances such as deviations, aberrant test results, or other "
- top-5 overlap: **5/5**

### 9. What training and personnel qualification records are required?

Filter: `source_agency=FDA, year_max=2018`

- pgvector top 3:
  - `DataIntegrity#13` (0.6676): "• §§ 211.22, 211.192, and 211.194(a) (requiring that production and control records be “reviewed” and that laboratory records be “reviewed for accuracy, completeness, and compliance with established s"
  - `Part11-Scope#17` (0.6426): "You should provide an investigator with reasonable and useful access to records during 280 an inspection. All records held by you are subject to inspection in accordance with predicate 281 rules (e.g."
  - `ProcessValidation#28` (0.6419): "The data collected should include relevant process trends and quality of incoming materials or components, in-process material, and finished products. The data should be statistically trended and revi"
- Qdrant top 3:
  - `DataIntegrity#13` (0.6676): "• §§ 211.22, 211.192, and 211.194(a) (requiring that production and control records be “reviewed” and that laboratory records be “reviewed for accuracy, completeness, and compliance with established s"
  - `Part11-Scope#17` (0.6426): "You should provide an investigator with reasonable and useful access to records during 280 an inspection. All records held by you are subject to inspection in accordance with predicate 281 rules (e.g."
  - `ProcessValidation#28` (0.6419): "The data collected should include relevant process trends and quality of incoming materials or components, in-process material, and finished products. The data should be statistically trended and revi"
- top-5 overlap: **5/5**

### 10. How should corrective and preventive actions be documented and verified?

Filter: `source_agency=FDA`

- pgvector top 3:
  - `CFR-58#9` (0.7745): "(f) Assure that personnel clearly understand the functions they are to perform. (g) Assure that any deviations from these regulations reported by the quality assurance unit are communicated to the stu"
  - `ProcessValidation#27` (0.7052): "• Evaluate any unexpected observations and additional data not specified in the protocol. • Summarize and discuss all manufacturing nonconformances such as deviations, aberrant test results, or other "
  - `ProcessValidation#30` (0.6966): "A description of the planned change, a well-justified rationale for the change, an implementation plan, and quality unit approval before implementation must be documented (§ 211.100). Depending on how"
- Qdrant top 3:
  - `CFR-58#9` (0.7745): "(f) Assure that personnel clearly understand the functions they are to perform. (g) Assure that any deviations from these regulations reported by the quality assurance unit are communicated to the stu"
  - `ProcessValidation#27` (0.7052): "• Evaluate any unexpected observations and additional data not specified in the protocol. • Summarize and discuss all manufacturing nonconformances such as deviations, aberrant test results, or other "
  - `ProcessValidation#30` (0.6966): "A description of the planned change, a well-justified rationale for the change, an implementation plan, and quality unit approval before implementation must be documented (§ 211.100). Depending on how"
- top-5 overlap: **5/5**

### Disagreement check

There were no top-5 disagreements: all ten queries had 5/5 overlap. Across the 50 shared top-5 chunks the maximum absolute score difference was `1.5e-07` and the mean difference was `5.2e-08`.

Reindexing Qdrant from Postgres (`python -m app.cli reindex --backend qdrant`)
is still the recovery path if the two stores diverge; it rebuilds the same 238
points from the canonical Postgres chunks.

## Filtered HNSW regression and result ordering

A selective-filter reproduction used 500 synthetic documents with 5 chunks each
(2,500 chunks). Five chunks belonged to a `Rare Agency` document whose vectors
were orthogonal to the query; the other 2,495 chunks dominated the nearest
neighbor candidate set. `enable_seqscan=off` forced the HNSW index and the
filter matched only the five rare chunks.

| Code path | Matching chunks | Returned with `top_k=50` |
| --- | ---: | ---: |
| Before fix | 5 | 0 |
| After iterative scan + exact fallback | 5 | 5 |

Filtered pgvector searches set `hnsw.iterative_scan = 'relaxed_order'`. If the
approximate result returns fewer rows than `top_k` and the exact matching count
is larger than the returned row count, the store retries with sequential scan
forced (`enable_seqscan=on`, `enable_indexscan=off`,
`enable_indexonlyscan=off`, `enable_bitmapscan=off`). This prioritizes
correctness for selective filters; the fallback only runs on observed
under-return.

`relaxed_order` is allowed to return candidates out of strict distance order, so
the store re-sorts the final hits by score descending after either the
approximate query or the fallback. A unit test feeds deliberately unordered
hits through the same sort helper and asserts descending scores.

## Metadata-only update semantics

Document identity is `(source_agency, filename)`; migration `0004` adds
`uq_documents_agency_filename`. Classification order is:

1. An existing global raw-byte SHA-256 is a duplicate of that content.
2. If the duplicate has the same identity, metadata fields (`title`,
   `doc_type`, `year`, `version`) are compared with the manifest. Changed
   fields update the `documents` row and the Qdrant payloads for that
   document's points. Chunk text, chunk IDs and vectors are untouched and no
   embedding call is made.
3. If the duplicate has a different identity, it remains a duplicate of the
   original document; renaming a file or changing its agency creates a new
   identity rather than rewriting the old one.
4. Same identity with a new content hash is an update: Postgres replaces the
   document metadata and all chunks in one transaction, then Qdrant points are
   replaced after commit.

The ingestion report now includes `documents_metadata_updated` and
`metadata_updates`, where each entry names the document and the changed fields.
Tests cover both upload and manifest metadata-only edits, assert the embedding
call count does not increase, and assert the Qdrant payload changes without
changing chunk IDs, text or scores.

## Failure reporting

If an external vector-store write fails after the Postgres transaction has
committed, the job error now states that Postgres committed the document and the
external index is out of date, and recommends
`python -m app.cli reindex --backend qdrant`. The injected-failure test asserts
that message, that the safe error does not leak the injected exception text, and
that re-ingesting the same content repairs Qdrant.

## Other condition checks

- `reindex --backend qdrant` rebuilt 8 documents / 238 chunks from Postgres. It
  is a delete-and-recreate operation, not an atomic cross-store transaction.
- Startup validates the configured embedder dimension, the Qdrant collection
  dimension, the Qdrant distance metric and the pgvector extension version. A
  mismatch raises a startup error.
- `top_k` is capped at 50 in both API schemas and store implementations.
  Unknown search/filter fields return HTTP 422.
- A real-lifespan test starts `create_app()` with Postgres, the fake embedder
  and Qdrant, uploads a document through the API, and retrieves it through the
  Qdrant backend.
