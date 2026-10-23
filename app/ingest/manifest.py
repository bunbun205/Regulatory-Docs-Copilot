import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.ingest.extract import SUPPORTED_EXTENSIONS

REQUIRED_COLUMNS = (
    "filename",
    "title",
    "source_agency",
    "doc_type",
    "year",
    "version",
)
MIN_YEAR = 1900
MAX_YEAR = 2100
FIELD_LIMITS = {
    "filename": 512,
    "title": 500,
    "source_agency": 200,
    "doc_type": 100,
    "version": 200,
}


class ManifestError(Exception):
    """Base class for manifest problems that prevent a run from starting."""


class ManifestSchemaError(ManifestError):
    """The manifest as a whole cannot be read or lacks required columns."""


@dataclass(frozen=True)
class ManifestRow:
    row_number: int
    filename: str
    title: str
    source_agency: str
    doc_type: str
    year: int
    version: str
    path: Path


@dataclass(frozen=True)
class RejectedRow:
    row_number: int
    filename: str | None
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Manifest:
    rows: tuple[ManifestRow, ...]
    rejected_rows: tuple[RejectedRow, ...]
    source_path: Path


def load_manifest(path: Path, documents_dir: Path) -> Manifest:
    """Load, validate and de-duplicate a corpus manifest with Pandas.

    Invalid rows are collected with reasons instead of aborting the run. A
    missing required column or an unreadable CSV is a schema error.
    """
    if not path.is_file():
        raise ManifestSchemaError("Manifest file was not found.")
    if not documents_dir.is_dir():
        raise ManifestSchemaError("Documents directory was not found.")

    try:
        frame = pd.read_csv(
            path,
            dtype=str,
            keep_default_na=False,
            na_filter=False,
            encoding="utf-8-sig",
        )
    except pd.errors.EmptyDataError as exc:
        raise ManifestSchemaError("Manifest is empty.") from exc
    except pd.errors.ParserError as exc:
        raise ManifestSchemaError("Manifest could not be parsed as CSV.") from exc

    frame.columns = [str(column).strip() for column in frame.columns]
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing_columns:
        raise ManifestSchemaError(
            "Manifest is missing required column(s): " + ", ".join(missing_columns)
        )
    if frame.empty:
        raise ManifestSchemaError("Manifest has no data rows.")

    documents_root = documents_dir.resolve()
    rows: list[ManifestRow] = []
    rejected: list[RejectedRow] = []
    seen_filenames: set[str] = set()

    for position, record in enumerate(frame.to_dict(orient="records"), start=1):
        row_number = position + 1
        values = {column: str(record.get(column, "")).strip() for column in REQUIRED_COLUMNS}
        filename = values["filename"] or None
        reasons: list[str] = []
        resolved_path: Path | None = None

        for field in ("filename", "title", "source_agency", "doc_type", "version"):
            if not values[field]:
                reasons.append(f"missing {field}")

        for field, limit in FIELD_LIMITS.items():
            if len(values[field]) > limit:
                reasons.append(f"{field} is too long (max {limit} characters)")

        if filename is not None:
            if filename in seen_filenames:
                reasons.append("duplicate filename")
            seen_filenames.add(filename)

            if Path(filename).name != filename or "/" in filename or "\\" in filename:
                reasons.append("filename must be a bare file name")
            else:
                suffix = Path(filename).suffix.lower()
                if suffix not in SUPPORTED_EXTENSIONS:
                    reasons.append(f"unsupported file type: {suffix or 'none'}")
                else:
                    candidate = documents_root / filename
                    try:
                        resolved_path = candidate.resolve(strict=True)
                    except (OSError, RuntimeError):
                        reasons.append("file not found")
                    else:
                        inside_root = resolved_path.is_relative_to(documents_root)
                        if not inside_root or not resolved_path.is_file():
                            reasons.append("file not found")

        raw_year = values["year"]
        if not raw_year:
            reasons.append("missing year")
        elif re.fullmatch(r"[0-9]{4}", raw_year) is None:
            reasons.append("year must be a four-digit number")
        else:
            parsed_year = int(raw_year)
            if not MIN_YEAR <= parsed_year <= MAX_YEAR:
                reasons.append(f"year must be between {MIN_YEAR} and {MAX_YEAR}")

        if reasons:
            rejected.append(
                RejectedRow(
                    row_number=row_number,
                    filename=filename,
                    reasons=tuple(dict.fromkeys(reasons)),
                )
            )
            continue

        assert resolved_path is not None
        rows.append(
            ManifestRow(
                row_number=row_number,
                filename=values["filename"],
                title=values["title"],
                source_agency=values["source_agency"],
                doc_type=values["doc_type"],
                year=int(values["year"]),
                version=values["version"],
                path=resolved_path,
            )
        )

    return Manifest(
        rows=tuple(rows),
        rejected_rows=tuple(rejected),
        source_path=path,
    )
