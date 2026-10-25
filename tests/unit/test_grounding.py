import json
from uuid import uuid4

from app.rag.grounding import citation_snippet, parse_answer_payload, validate_answer
from app.store.base import SearchHit


def _hit(text: str = "Source text.") -> SearchHit:
    return SearchHit(
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        text=text,
        score=0.9,
        page=4,
        section_heading=None,
        filename="doc.pdf",
        title="Document",
        source_agency="FDA",
        doc_type="guidance",
        year=2024,
        version="v1",
    )


def test_valid_json_with_known_citation_is_grounded() -> None:
    hit = _hit()
    result = validate_answer(
        json.dumps({"answer": "Use controls.", "citations": [str(hit.chunk_id)]}),
        [hit],
    )

    assert result.grounded is True
    assert result.reason is None
    assert result.answer == "Use controls."
    assert result.citations == (hit,)


def test_json_inside_markdown_fence_is_accepted() -> None:
    hit = _hit()
    payload = json.dumps({"answer": "Fenced answer.", "citations": [str(hit.chunk_id)]})
    result = validate_answer(f"```json\n{payload}\n```", [hit])

    assert result.grounded is True
    assert result.answer == "Fenced answer."


def test_unknown_citation_is_removed_and_flags_ungrounded() -> None:
    hit = _hit()
    result = validate_answer(
        json.dumps(
            {
                "answer": "Mixed citations.",
                "citations": [str(hit.chunk_id), str(uuid4())],
            }
        ),
        [hit],
    )

    assert result.grounded is False
    assert result.reason == "invalid_citations_removed"
    assert result.citations == (hit,)


def test_no_valid_citations_is_ungrounded() -> None:
    result = validate_answer(
        json.dumps({"answer": "Invented.", "citations": [str(uuid4())]}),
        [_hit()],
    )

    assert result.grounded is False
    assert result.reason == "no_valid_citations"
    assert result.citations == ()


def test_malformed_json_is_ungrounded_but_preserves_safe_text() -> None:
    result = validate_answer("not json", [_hit()])

    assert result.grounded is False
    assert result.reason == "invalid_json"
    assert result.answer == "not json"


def test_missing_answer_is_ungrounded() -> None:
    result = validate_answer(json.dumps({"citations": []}), [_hit()])

    assert result.grounded is False
    assert result.reason == "empty_answer"


def test_citation_snippet_normalizes_whitespace() -> None:
    assert citation_snippet("a\n\n  b\tc", limit=10) == "a b c"
    assert citation_snippet("abcdefghij", limit=5) == "abcde"


def test_parse_answer_payload_returns_none_for_non_object() -> None:
    assert parse_answer_payload("[1, 2]") is None
