from pathlib import Path

import pytest

from app.ingest.manifest import ManifestSchemaError, load_manifest


def test_sample_manifest_has_valid_and_rejected_rows(sample_dir: Path) -> None:
    manifest = load_manifest(sample_dir / "manifest.csv", sample_dir)

    assert [row.filename for row in manifest.rows] == [
        "synthetic-lab-policy.pdf",
        "synthetic-lab-procedure.md",
        "synthetic-training-notes.txt",
        "synthetic-lab-procedure-copy.md",
    ]
    assert [row.year for row in manifest.rows] == [2024, 2024, 2023, 2024]

    rejected = {row.row_number: row for row in manifest.rejected_rows}
    assert set(rejected) == {6, 7, 8}
    assert "missing title" in rejected[6].reasons
    assert "duplicate filename" in rejected[6].reasons
    assert rejected[7].filename == "synthetic-missing.pdf"
    assert "file not found" in rejected[7].reasons
    assert "year must be a four-digit number" in rejected[8].reasons
    assert "duplicate filename" in rejected[8].reasons


def test_missing_required_column_is_schema_error(tmp_path: Path) -> None:
    documents = tmp_path / "documents"
    documents.mkdir()
    manifest_path = tmp_path / "manifest.csv"
    manifest_path.write_text(
        "filename,title,source_agency,doc_type,year\n"
        "note.txt,Note,Synthetic Agency,guidance,2024\n",
        encoding="utf-8",
    )

    with pytest.raises(ManifestSchemaError, match="version"):
        load_manifest(manifest_path, documents)


def test_header_only_manifest_is_schema_error(tmp_path: Path) -> None:
    documents = tmp_path / "documents"
    documents.mkdir()
    manifest_path = tmp_path / "manifest.csv"
    manifest_path.write_text(
        "filename,title,source_agency,doc_type,year,version\n",
        encoding="utf-8",
    )

    with pytest.raises(ManifestSchemaError, match="no data rows"):
        load_manifest(manifest_path, documents)


def test_path_traversal_is_rejected(tmp_path: Path) -> None:
    documents = tmp_path / "documents"
    documents.mkdir()
    (tmp_path / "outside.txt").write_text("outside", encoding="utf-8")
    manifest_path = tmp_path / "manifest.csv"
    manifest_path.write_text(
        "filename,title,source_agency,doc_type,year,version\n"
        "../outside.txt,Outside,Synthetic Agency,guidance,2024,v1\n",
        encoding="utf-8",
    )

    manifest = load_manifest(manifest_path, documents)

    assert manifest.rows == ()
    assert len(manifest.rejected_rows) == 1
    assert "filename must be a bare file name" in manifest.rejected_rows[0].reasons


def test_out_of_range_year_and_unsupported_extension_are_rejected(
    tmp_path: Path,
) -> None:
    documents = tmp_path / "documents"
    documents.mkdir()
    (documents / "old.txt").write_text("old", encoding="utf-8")
    (documents / "table.csv").write_text("a,b\n", encoding="utf-8")
    (documents / "long-title.txt").write_text("long", encoding="utf-8")
    manifest_path = tmp_path / "manifest.csv"
    manifest_path.write_text(
        "filename,title,source_agency,doc_type,year,version\n"
        "old.txt,Old,Synthetic Agency,guidance,1800,v1\n"
        "table.csv,Table,Synthetic Agency,guidance,2024,v1\n"
        f"long-title.txt,{'x' * 501},Synthetic Agency,guidance,2024,v1\n",
        encoding="utf-8",
    )

    manifest = load_manifest(manifest_path, documents)
    reasons = {rejected.filename: rejected.reasons for rejected in manifest.rejected_rows}

    assert manifest.rows == ()
    assert "year must be between 1900 and 2100" in reasons["old.txt"]
    assert any("unsupported file type" in reason for reason in reasons["table.csv"])
    assert any("title is too long" in reason for reason in reasons["long-title.txt"])
