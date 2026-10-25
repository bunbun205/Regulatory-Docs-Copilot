from uuid import uuid4

from app.gapcheck.requirements import extract_requirements
from app.store.base import SearchHit


def _hit(text: str, *, chunk_id=None, score: float = 0.9) -> SearchHit:
    return SearchHit(
        chunk_id=chunk_id or uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        text=text,
        score=score,
        page=4,
        section_heading="Records",
        filename="records.pdf",
        title="Records Regulation",
        source_agency="FDA",
        doc_type="regulation",
        year=2024,
        version="v1",
    )


def test_extract_requirements_marks_mandatory_and_advisory() -> None:
    requirements, capped = extract_requirements(
        [
            _hit(
                "The laboratory manager shall review records annually. "
                "Staff should document training. This is descriptive. "
                "Records must be retained for five years."
            )
        ]
    )

    assert capped is False
    assert [requirement.strength for requirement in requirements] == [
        "mandatory",
        "advisory",
        "mandatory",
    ]
    assert requirements[0].requirement_id == "REQ-001"
    assert requirements[1].text == "Staff should document training."
    assert requirements[2].text.startswith("Records must")
    assert requirements[0].chunk_id


def test_extract_requirements_inherits_strength_for_enumerated_items() -> None:
    requirements, capped = extract_requirements(
        [
            _hit(
                "The system shall include the following: "
                "(a) Validation of systems. "
                "(b) Use of authority checks to ensure that only authorized "
                "individuals can use the system. "
                "(c) Handwritten signature means a scripted name."
            )
        ]
    )

    assert capped is False
    assert [requirement.text for requirement in requirements] == [
        "(a) Validation of systems.",
        "(b) Use of authority checks to ensure that only authorized individuals "
        "can use the system.",
    ]
    assert all(requirement.strength == "mandatory" for requirement in requirements)


def test_extract_requirements_deduplicates_and_caps() -> None:
    text = "The SOP shall control records. The SOP shall control records."
    requirements, capped = extract_requirements([_hit(text)], max_requirements=10)
    assert len(requirements) == 1
    assert capped is False

    many = " ".join(f"Control {index} shall be documented." for index in range(5))
    requirements, capped = extract_requirements([_hit(many)], max_requirements=2)
    assert len(requirements) == 2
    assert capped is True
    assert [requirement.requirement_id for requirement in requirements] == [
        "REQ-001",
        "REQ-002",
    ]
