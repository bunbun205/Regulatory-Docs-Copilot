from datetime import UTC, datetime
from uuid import uuid4

from app.gapcheck.report import (
    BANNER,
    build_report,
    citation_from_hit,
    make_finding,
    severity_for,
    suggested_fix,
)
from app.store.base import SearchHit


def _hit() -> SearchHit:
    return SearchHit(
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        text="Records shall be retained for five years.",
        score=0.9123456,
        page=2,
        section_heading="Records",
        filename="records.pdf",
        title="Records Regulation",
        source_agency="FDA",
        doc_type="regulation",
        year=2024,
        version="v1",
    )


def test_severity_rule_is_deterministic() -> None:
    assert severity_for("conflict", None) == "high"
    assert severity_for("missing", "mandatory") == "high"
    assert severity_for("missing", "advisory") == "medium"
    assert severity_for("partial", None) == "medium"
    assert severity_for("partially_addressed", "mandatory") == "medium"
    assert severity_for("compliant", None) == "low"
    assert severity_for("addressed", "advisory") == "medium"
    assert severity_for("judge_failed", "mandatory") == "low"


def test_suggested_fix_is_labelled() -> None:
    assert suggested_fix("conflict").startswith("Suggested fix (not legal advice):")


def test_build_report_numbers_findings_and_counts() -> None:
    hit = _hit()
    finding = make_finding(
        direction="sop_to_regulation",
        verdict="conflict",
        sop_clause_refs=["SOP-001"],
        regulation_citations=[citation_from_hit(hit)],
        rationale="The SOP contradicts the retention requirement.",
    )
    report = build_report(
        job_id=str(uuid4()),
        sop_clauses=[
            {
                "clause_id": "SOP-001",
                "section": "Records",
                "text": "Destroy records after one year.",
                "char_start": 0,
                "char_end": 31,
            }
        ],
        findings=[finding],
        metadata={"model": "fake:fake"},
        caps_hit=[],
        generated_at=datetime.now(UTC),
    )

    assert report["banner"] == BANNER
    assert report["findings"][0]["finding_id"] == "GAP-0001"
    assert report["findings"][0]["severity"] == "high"
    assert report["counts_by_verdict"]["conflict"] == 1
    assert report["counts_by_severity"]["high"] == 1
    assert report["counts_by_direction"]["sop_to_regulation"] == 1
    assert report["findings"][0]["regulation_citations"][0]["score"] == 0.912346
    assert report["findings"][0]["suggested_fix"].startswith("Suggested fix")
