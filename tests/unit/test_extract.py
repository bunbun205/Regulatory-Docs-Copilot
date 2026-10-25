from pathlib import Path

import pytest

from app.ingest.extract import (
    ExtractionError,
    extract_document,
    strip_cross_page_boilerplate,
)


def test_extract_pdf_preserves_page_numbers(sample_dir: Path) -> None:
    extracted = extract_document(sample_dir / "synthetic-lab-policy.pdf")

    assert extracted.page_count == 2
    assert [block.page for block in extracted.blocks] == [1, 2]
    assert "SYNTHETIC LABORATORY SAFETY POLICY" in extracted.blocks[0].text
    assert "4. Incident Reporting" in extracted.blocks[1].text
    assert all(block.section_heading is None for block in extracted.blocks)


def test_extract_markdown_preserves_headings(sample_dir: Path) -> None:
    extracted = extract_document(sample_dir / "synthetic-lab-procedure.md")

    assert extracted.page_count is None
    headings = [block.section_heading for block in extracted.blocks]
    assert "1. Scope" in headings
    assert "4. Disposal" in headings
    assert all(block.page is None for block in extracted.blocks)


def test_extract_text_file(sample_dir: Path) -> None:
    extracted = extract_document(sample_dir / "synthetic-training-notes.txt")

    assert extracted.page_count is None
    assert len(extracted.blocks) == 1
    assert extracted.blocks[0].page is None
    assert extracted.blocks[0].section_heading is None
    assert "SYNTHETIC TRAINING NOTES" in extracted.blocks[0].text


def test_duplicate_markdown_file_is_byte_identical(sample_dir: Path) -> None:
    original = (sample_dir / "synthetic-lab-procedure.md").read_bytes()
    duplicate = (sample_dir / "synthetic-lab-procedure-copy.md").read_bytes()
    assert original == duplicate


def test_unsupported_extension_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "table.csv"
    path.write_text("a,b\n", encoding="utf-8")

    with pytest.raises(ExtractionError, match="Unsupported file type"):
        extract_document(path)


def test_invalid_pdf_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"this is not a pdf")

    with pytest.raises(ExtractionError, match="PDF"):
        extract_document(path)


def test_blank_text_file_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "blank.txt"
    path.write_text(" \n\n\t", encoding="utf-8")

    with pytest.raises(ExtractionError, match="no extractable text"):
        extract_document(path)


def test_non_utf8_text_file_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "binary.txt"
    path.write_bytes(b"\xff\xfe\x00\x01")

    with pytest.raises(ExtractionError, match="UTF-8"):
        extract_document(path)


def test_cross_page_boilerplate_is_stripped_but_content_is_kept() -> None:
    pages = [
        (
            "Guidance for Industry\n"
            "This content is from the eCFR and is authoritative but unofficial.\n"
            "21 CFR Part 211 (up to date as of 10/21/2026)\n"
            "10/23/26, 4:40 PM 1910.1200 - Hazard Communication. | "
            "Occupational Safety and Health Administration\n"
            "The first substantive paragraph.\n"
            "Current Good Manufacturing Practice 21 CFR Part 211 (Oct. 21, 2026)\n"
            "21 CFR Part 211 (Oct. 21, 2026) (enhanced display) page 1 of 3\n"
            "https://www.osha.gov/laws-regs/standardnumber/1910/1910.1200 1/3"
        ),
        (
            "Contains Nonbinding Recommendations\n"
            "The second substantive paragraph.\n"
            "Scroll to Top\n"
            "Connect With OSHA\n"
            "Important Website Notices\n"
            "https://www.osha.gov/laws-regs/standardnumber/1910/1910.1200 2/3\n"
            "2"
        ),
        (
            "Contains Nonbinding Recommendations\n"
            "The third substantive paragraph.\n"
            "Privacy & Security Statement\n"
            "https://www.osha.gov/laws-regs/standardnumber/1910/1910.1200 3/3\n"
            "3"
        ),
    ]

    cleaned = strip_cross_page_boilerplate(pages)

    assert cleaned == [
        "Guidance for Industry\nThe first substantive paragraph.",
        "The second substantive paragraph.",
        "The third substantive paragraph.",
    ]


def test_repeated_short_lines_are_detected_even_when_page_numbers_vary() -> None:
    pages = [
        "Running title page 1 of 3\nAlpha body.",
        "Running title page 2 of 3\nBeta body.",
        "Running title page 3 of 3\nGamma body.",
    ]

    cleaned = strip_cross_page_boilerplate(pages)

    assert cleaned == ["Alpha body.", "Beta body.", "Gamma body."]


def test_sample_pdf_still_extracts_substantive_text() -> None:
    extracted = extract_document(
        Path(__file__).resolve().parents[2] / "data" / "sample" / "synthetic-lab-policy.pdf"
    )

    assert "SYNTHETIC LABORATORY SAFETY POLICY" in extracted.blocks[0].text
    assert "4. Incident Reporting" in extracted.blocks[1].text
