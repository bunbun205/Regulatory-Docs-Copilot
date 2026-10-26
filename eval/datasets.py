"""Dataset contracts. A candidate never becomes ground truth implicitly."""

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Reviewable(Record):
    id: str = Field(min_length=1)
    verified: StrictBool = False
    reviewed_by: str | None = None
    reviewed_at: date | None = None
    notes: str = ""

    @model_validator(mode="after")
    def require_review(self) -> Self:
        if self.verified and (not (self.reviewed_by or "").strip() or self.reviewed_at is None):
            raise ValueError("Verified entries require reviewed_by and reviewed_at.")
        return self


class SourceLocation(Record):
    filename: str = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page: int | None = Field(default=None, ge=1)
    section: str | None = None
    quote: str = Field(min_length=1)

    @model_validator(mode="after")
    def location_required(self) -> Self:
        if self.page is None and not (self.section or "").strip():
            raise ValueError("Expected sources require a page or section.")
        return self


class Question(Reviewable):
    question: str = Field(min_length=1)
    kind: Literal["answerable", "multi_document", "unanswerable"]
    expected_sources: list[SourceLocation] = Field(default_factory=list)
    corpus_snapshot: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def check_sources(self) -> Self:
        if self.verified and self.kind == "unanswerable" and self.corpus_snapshot is None:
            raise ValueError("Verified unanswerables must be bound to a corpus snapshot.")
        if self.kind == "unanswerable" and self.expected_sources:
            raise ValueError("Unanswerable questions cannot have expected sources.")
        if self.kind != "unanswerable" and not self.expected_sources:
            raise ValueError("Answerable questions require candidate sources, even before review.")
        if self.kind == "multi_document" and len({s.filename for s in self.expected_sources}) < 2:
            raise ValueError("Multi-document questions require at least two source documents.")
        if len({s.model_dump_json() for s in self.expected_sources}) != len(self.expected_sources):
            raise ValueError("Duplicate source targets distort recall.")
        return self


class Defect(Record):
    id: str = Field(min_length=1)
    direction: Literal["sop_to_regulation", "regulation_to_sop"]
    verdicts: list[Literal["conflict", "partial", "missing", "partially_addressed"]]
    source: SourceLocation
    sop_quote: str | None = None
    requirement_quote: str | None = None
    description: str = Field(min_length=1)

    @model_validator(mode="after")
    def require_targets(self) -> Self:
        if not self.verdicts:
            raise ValueError("A defect must specify accepted verdicts.")
        if self.direction == "sop_to_regulation" and not self.sop_quote:
            raise ValueError("SOP-to-regulation defects require a matching SOP quote.")
        if self.direction == "regulation_to_sop" and not self.requirement_quote:
            raise ValueError("Omission defects require a quote from the requirement citation.")
        allowed = (
            {"conflict", "partial"}
            if self.direction == "sop_to_regulation"
            else {"missing", "partially_addressed"}
        )
        if not set(self.verdicts) <= allowed:
            raise ValueError("Defect verdicts must match the analysis direction.")
        return self


class GapCase(Reviewable):
    kind: Literal["clean", "mutation"]
    sop_path: str = Field(min_length=1)
    sop_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance: str = Field(min_length=1)
    corpus_snapshot: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    baseline_id: str | None = None
    defects: list[Defect] = Field(default_factory=list)
    filters: dict[str, str | int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def baseline_required(self) -> Self:
        if self.verified and self.corpus_snapshot is None:
            raise ValueError("Verified gap cases must be bound to a corpus snapshot.")
        if self.kind == "mutation" and (not self.baseline_id or not self.defects):
            raise ValueError("Mutations require a clean baseline and explicit defects.")
        if self.kind == "clean" and (self.baseline_id or self.defects):
            raise ValueError("Clean baselines cannot contain injected defects.")
        if len({d.id for d in self.defects}) != len(self.defects):
            raise ValueError("Defect IDs must be unique within a case.")
        return self


class CleanReview(Record):
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewed_by: str = Field(min_length=1)
    reviewed_at: date
    false_positive_ids: list[str]
    notes: str = ""


def load_jsonl[T: Reviewable](path: Path, model: type[T]) -> list[T]:
    result: list[T] = []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            result.append(model.model_validate(json.loads(line)))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid {path.name} record on line {number}: {exc}") from exc
    if len({row.id for row in result}) != len(result):
        raise ValueError(f"Duplicate IDs in {path.name}.")
    return result


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report_hash(report: dict) -> str:
    """Bind human finding review to the exact report, including model and run."""
    return hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()
