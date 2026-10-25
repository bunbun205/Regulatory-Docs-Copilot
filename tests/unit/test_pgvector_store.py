from uuid import uuid4

from app.store.base import SearchHit
from app.store.pgvector_store import pgvector_supports_iterative_scan, sort_hits_by_score


def _hit(score: float) -> SearchHit:
    return SearchHit(
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        text="text",
        score=score,
        page=None,
        section_heading=None,
        filename="file.txt",
        title="Title",
        source_agency="Agency",
        doc_type="guidance",
        year=2024,
        version="v1",
    )


def test_relaxed_order_results_are_resorted_by_score_descending() -> None:
    low = _hit(0.42)
    high = _hit(0.91)
    middle = _hit(0.73)

    assert sort_hits_by_score([low, high, middle]) == [high, middle, low]


def test_iterative_scan_version_gate() -> None:
    assert pgvector_supports_iterative_scan("0.8.0")
    assert pgvector_supports_iterative_scan("0.8.7")
    assert pgvector_supports_iterative_scan("0.10.1")
    assert not pgvector_supports_iterative_scan("0.7.4")
    assert not pgvector_supports_iterative_scan("not-a-version")
