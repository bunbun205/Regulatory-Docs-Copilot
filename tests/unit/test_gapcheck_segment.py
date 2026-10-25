import pandas as pd
import pytest

from app.gapcheck.segment import (
    SOP_CLAUSE_COLUMNS,
    ClauseCapExceeded,
    EmptySopError,
    normalize_sop_text,
    segment_sop,
)

SOP_TEXT = """# Document Control
SOP-001 Rev 4
Page 1 of 3
Effective Date: 2026-01-01

# Purpose
This SOP describes how training records are retained.

1. Scope
This SOP applies to all laboratory staff.

2. Responsibilities
The laboratory manager shall review training records annually.

Approved by: Jane Doe
Signature: J. Doe
Date: 2026-01-01

| Rev | Date | Change |
| --- | --- | --- |
| 1.0 | 2026-01-01 | Initial release |

# Revision History
No further entries.
"""


def test_segment_sop_returns_clauses_with_exact_offsets() -> None:
    frame = segment_sop(SOP_TEXT, max_clauses=80)

    assert list(frame.columns) == SOP_CLAUSE_COLUMNS
    assert isinstance(frame, pd.DataFrame)
    assert frame["clause_id"].tolist() == ["SOP-001", "SOP-002", "SOP-003"]
    assert frame["section"].tolist() == ["Purpose", "Purpose", "Purpose"]
    assert frame["text"].iloc[0] == "This SOP describes how training records are retained."
    assert frame["text"].iloc[1].startswith("1. Scope")
    assert "laboratory manager shall" in frame["text"].iloc[2]

    normalized = normalize_sop_text(SOP_TEXT)
    for row in frame.itertuples(index=False):
        assert normalized[row.char_start : row.char_end] == row.text


def test_segment_sop_removes_page_furniture_signatures_and_revision_tables() -> None:
    frame = segment_sop(SOP_TEXT)
    combined = "\n".join(frame["text"].tolist())

    assert "Page 1 of 3" not in combined
    assert "SOP-001 Rev 4" not in combined
    assert "Approved by" not in combined
    assert "Signature" not in combined
    assert "| Rev |" not in combined
    assert "Revision History" not in combined


def test_segment_sop_keeps_non_furniture_tables() -> None:
    text = """# Training Matrix
| Role | Training |
| --- | --- |
| Analyst | GLP |
| Reviewer | Data integrity |
"""

    frame = segment_sop(text)
    combined = "\n".join(frame["text"].tolist())

    assert "| Role | Training |" in combined
    assert "Analyst" in combined
    assert "Reviewer" in combined


def test_segment_sop_rejects_over_cap() -> None:
    text = "\n\n".join(f"Paragraph {index} describes a distinct control." for index in range(81))

    with pytest.raises(ClauseCapExceeded, match="81 clauses"):
        segment_sop(text, max_clauses=80)


def test_segment_sop_rejects_empty_text() -> None:
    with pytest.raises(EmptySopError):
        segment_sop("  \n\n  ")
