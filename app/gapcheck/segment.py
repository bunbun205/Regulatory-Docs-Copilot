"""Deterministic SOP clause segmentation.

The segmenter is intentionally conservative: it keeps exact character offsets
for every clause so the report can point back to the source text, and it drops
common document furniture before the clause cap is applied.
"""

import re
from dataclasses import dataclass

import pandas as pd

SOP_CLAUSE_COLUMNS = ["clause_id", "section", "text", "char_start", "char_end"]

_MARKDOWN_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
_SECTION_HEADING = re.compile(
    r"^\s*(?:section|article)\s+[0-9IVX]+[.:)]?\s+(.+?)\s*$",
    re.I,
)
_ALLCAPS_HEADING = re.compile(r"^[A-Z0-9][A-Z0-9 &/()\-.,']{2,100}$")
_NUMBERED_ITEM = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*[.)]?|[A-Za-z][.)]|\([a-z]\))\s+\S",
    re.I,
)

_BOILERPLATE_EXACT = frozenset(
    {
        "confidential",
        "controlled document",
        "document control",
        "internal use only",
        "revision history",
        "change history",
        "table of contents",
        "no further entries",
        "no revisions",
    }
)
_FURNITURE_SECTIONS = frozenset(
    {
        "revision history",
        "change history",
        "document history",
        "version history",
        "table of contents",
    }
)
_REVISION_TABLE_HEADER = re.compile(
    r"^\s*\|\s*(?:rev(?:ision)?|version)\b.*\|\s*$",
    re.I,
)
_BOILERPLATE_PATTERNS = (
    re.compile(r"^\s*page\s+\d+(?:\s+of\s+\d+)?\s*$", re.I),
    re.compile(r"^\s*\d+\s*/\s*\d+\s*$"),
    re.compile(r"^\s*(?:https?://|www\.)\S+\s*$", re.I),
    re.compile(r"^\s*(?:document|doc)\s*(?:id|number|no\.?)\s*[:#-]", re.I),
    re.compile(
        r"^\s*(?:effective|revision|review|date|approved|prepared|reviewed|supersedes|"
        r"next review)\s*(?:date)?\s*[:#-]",
        re.I,
    ),
    re.compile(r"^\s*(?:approved|prepared|reviewed|authorized)\s+by\s*[:#-]?", re.I),
    re.compile(r"^\s*(?:signature|signed)\s*[:#-]?", re.I),
    re.compile(r"^\s*(?:name|title|department)\s*[:#-]", re.I),
    re.compile(r"^\s*(?:rev(?:ision)?|version)\s*[:#]?\s*\d", re.I),
    re.compile(r"^\s*[A-Z]{2,12}-[A-Z0-9-]+\s+(?:rev|version)\b", re.I),
    re.compile(r"^\s*[-|: ]{3,}\s*$"),
    re.compile(r"^no (?:further )?(?:entries|changes|revisions)\.?$", re.I),
)


class GapCheckInputError(Exception):
    """The SOP cannot be segmented into a bounded, usable clause set."""


class EmptySopError(GapCheckInputError):
    """The submitted SOP contains no usable clauses."""


class ClauseCapExceeded(GapCheckInputError):
    """The SOP has more clauses than the configured hard cap."""


@dataclass(frozen=True)
class SopClause:
    clause_id: str
    section: str
    text: str
    char_start: int
    char_end: int


def normalize_sop_text(text: str) -> str:
    """Normalize line endings and control characters without changing offsets."""
    text = text.replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\x0c", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def segment_sop(text: str, *, max_clauses: int = 80) -> pd.DataFrame:
    """Segment an SOP into ``clause_id, section, text, char_start, char_end``.

    Headings set the section for following clauses. Markdown headings,
    Section/Article headings and all-caps headings are recognised; numbered
    items and blank-line-separated paragraphs start new clauses. Common page
    furniture, signature fields and revision tables are removed first.
    """
    normalized = normalize_sop_text(text)
    if not normalized:
        raise EmptySopError("SOP contains no extractable text.")
    clauses = _segment_rows(normalized)
    if not clauses:
        raise EmptySopError("SOP contains no usable clauses after boilerplate removal.")
    if len(clauses) > max_clauses:
        raise ClauseCapExceeded(
            f"SOP has {len(clauses)} clauses; the maximum is {max_clauses}. "
            "Split the SOP or raise the clause cap explicitly."
        )
    return pd.DataFrame(
        [
            {
                "clause_id": clause.clause_id,
                "section": clause.section,
                "text": clause.text,
                "char_start": clause.char_start,
                "char_end": clause.char_end,
            }
            for clause in clauses
        ],
        columns=SOP_CLAUSE_COLUMNS,
    )


def _segment_rows(text: str) -> list[SopClause]:
    clauses: list[SopClause] = []
    current_section = "General"
    current: list[tuple[str, int, int]] = []
    in_furniture_section = False
    in_revision_table = False

    def flush() -> None:
        nonlocal current
        if not current:
            return
        start = current[0][1]
        end = current[-1][2]
        raw = text[start:end]
        left = len(raw) - len(raw.lstrip())
        right = len(raw) - len(raw.rstrip())
        start += left
        end -= right
        clause_text = text[start:end]
        if clause_text:
            clauses.append(
                SopClause(
                    clause_id=f"SOP-{len(clauses) + 1:03d}",
                    section=current_section,
                    text=clause_text,
                    char_start=start,
                    char_end=end,
                )
            )
        current = []

    for content, start, end, is_blank in _line_infos(text):
        if is_blank:
            flush()
            in_revision_table = False
            continue
        heading = _heading_text(content)
        if heading is not None:
            flush()
            current_section = heading
            in_furniture_section = heading.casefold() in _FURNITURE_SECTIONS
            in_revision_table = False
            continue
        if in_furniture_section:
            continue
        if _REVISION_TABLE_HEADER.match(content):
            flush()
            in_revision_table = True
            continue
        if in_revision_table:
            if content.startswith("|"):
                continue
            in_revision_table = False
        if _is_boilerplate(content):
            flush()
            continue
        if _NUMBERED_ITEM.match(content):
            flush()
            current.append((content, start, end))
            continue
        current.append((content, start, end))
    flush()
    return clauses


def _line_infos(text: str) -> list[tuple[str, int, int, bool]]:
    infos: list[tuple[str, int, int, bool]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\n")
        content = body.strip()
        if content:
            start = offset + (len(body) - len(body.lstrip()))
            end = offset + len(body.rstrip())
            infos.append((content, start, end, False))
        else:
            infos.append(("", offset, offset, True))
        offset += len(line)
    return infos


def _heading_text(content: str) -> str | None:
    match = _MARKDOWN_HEADING.match(content)
    if match:
        return match.group(1).strip()
    match = _SECTION_HEADING.match(content)
    if match:
        return match.group(1).strip()
    if _ALLCAPS_HEADING.match(content) and any(character.isalpha() for character in content):
        return content.strip()
    return None


def _is_boilerplate(content: str) -> bool:
    normalized = re.sub(r"\s+", " ", content).strip()
    if normalized.casefold() in _BOILERPLATE_EXACT:
        return True
    return any(pattern.search(normalized) for pattern in _BOILERPLATE_PATTERNS)
