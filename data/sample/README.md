# Synthetic ingestion fixture

Everything in this directory is **synthetic test data**. None of it is a real
regulation, agency document, guidance, procedure, or training record, and none
of it must be used for evaluation numbers or presented as corpus content.

The fixture exists to exercise the ingestion pipeline without a network
dependency on the real corpus. It contains:

| File | Purpose |
|---|---|
| `synthetic-lab-policy.pdf` | PDF extraction and page preservation |
| `synthetic-lab-procedure.md` | Markdown heading/section extraction |
| `synthetic-lab-procedure-copy.md` | Byte-identical copy of the Markdown file; must be rejected by content-hash dedupe |
| `synthetic-training-notes.txt` | Plain-text extraction |
| `manifest.csv` | Four valid rows plus three deliberately malformed rows |

The manifest has these expected outcomes:

- 4 valid rows (including both copies of the Markdown procedure).
- 3 rejected rows:
  - row 6: missing title (and a duplicate filename)
  - row 7: filename does not exist in this directory
  - row 8: non-numeric year (and a duplicate filename)
- On first ingestion: 3 unique documents, 1 content-hash duplicate, 3 rejected rows.
- On a second ingestion: 0 new documents, 4 content-hash duplicates, 3 rejected rows.
- Document/chunk counts must not change between runs.

Row numbers in the ingestion report count the CSV header as row 1.
