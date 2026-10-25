import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

SUPPORTED_EXTENSIONS = {".pdf", ".md", ".markdown", ".txt"}
_MARKDOWN_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")

# Lines that are recognisable cross-page furniture rather than document text.
# The list covers eCFR print output, OSHA browser print output and the FDA
# guidance running header/footer.
_BOILERPLATE_LINE_PATTERNS = (
    re.compile(r"^this content is from the ecfr and is authoritative but unofficial\.?$", re.I),
    re.compile(r"^contains nonbinding recommendations$", re.I),
    re.compile(r"^21 cfr part \d+ \(up to date as of .+\)$", re.I),
    re.compile(r"^.+ 21 cfr part \d+ \([a-z]{3}\. \d{1,2}, \d{4}\)$", re.I),
    re.compile(
        r"^(?:electronic records; electronic signatures|"
        r"current good manufacturing practice for finished pharmaceuticals|"
        r"good laboratory practice for nonclinical laboratory studies) "
        r"21 cfr \d+(?:\.\d+)?(?:\([^)]*\))*$",
        re.I,
    ),
    re.compile(r"\(enhanced display\)\s+page\s+\d+\s+of\s+\d+$", re.I),
    re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4},\s+\d{1,2}:\d{2}\s*(?:am|pm)\b", re.I),
    re.compile(r"^(?:https?://|www\.)\S+(?:\s+\d+/\d+)?$", re.I),
    re.compile(r"^\d{1,3}(?:\s*/\s*\d{1,3})?$"),
    re.compile(r"^page\s+\d+\s+of\s+\d+$", re.I),
    re.compile(r"^\d+\s+of\s+\d+$", re.I),
)
_BOILERPLATE_EXACT_LINES = frozenset(
    {
        "a - z index",
        "about the site",
        "accessibility statement",
        "connect with osha",
        "disaster recovery assistance",
        "disasterassistance.gov",
        "disclaimers",
        "federal government",
        "freedom of information act",
        "freedom of information act - osha",
        "frequently asked questions",
        "important website notices",
        "no fear act data",
        "occupational safety & health",
        "occupational safety and health administration",
        "office of inspector general",
        "osha publications",
        "osha standards enforcement topics media center contact us",
        "plug-ins used on dol.gov",
        "privacy & security statement",
        "read the osha newsletter",
        "scroll to top",
        "site map",
        "site map important website notices privacy & security statement",
        "subscribe to the osha newsletter",
        "u.s. department of labor",
        "u.s. office of special counsel",
        "usa.gov",
        "white house",
        "www.osha.gov",
        "1-800-321-osha",
        "1-800-321-6742",
        "200 constitution ave nw",
        "washington, dc 20210",
    }
)


class ExtractionError(Exception):
    """A document could not be converted into text."""


@dataclass(frozen=True)
class TextBlock:
    text: str
    page: int | None
    section_heading: str | None


@dataclass(frozen=True)
class ExtractedDocument:
    blocks: tuple[TextBlock, ...]
    page_count: int | None


def extract_document(path: Path) -> ExtractedDocument:
    """Extract text and location metadata from a supported document."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(path)
    if suffix in {".md", ".markdown"}:
        return _extract_markdown(path)
    if suffix == ".txt":
        return _extract_text_file(path)
    raise ExtractionError(f"Unsupported file type: {suffix or 'none'}.")


def _extract_pdf(path: Path) -> ExtractedDocument:
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted and reader.decrypt("") == 0:
            raise ExtractionError("PDF is encrypted and cannot be read.")
        page_texts: list[str] = []
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                raw_text = page.extract_text() or ""
            except Exception as exc:
                raise ExtractionError(
                    f"Could not extract text from PDF page {page_number}."
                ) from exc
            page_texts.append(_normalize_text(raw_text))
        page_count = len(reader.pages)
    except ExtractionError:
        raise
    except (PdfReadError, OSError, ValueError, TypeError) as exc:
        raise ExtractionError("PDF could not be read.") from exc

    cleaned_pages = strip_cross_page_boilerplate(page_texts)
    blocks = [
        TextBlock(text=text, page=page_number, section_heading=None)
        for page_number, text in enumerate(cleaned_pages, start=1)
        if text
    ]
    if not blocks:
        raise ExtractionError("PDF contains no extractable text.")
    return ExtractedDocument(blocks=tuple(blocks), page_count=page_count)


def strip_cross_page_boilerplate(page_texts: list[str]) -> list[str]:
    """Remove repeated print headers/footers, URLs and navigation furniture.

    The extractor keeps one text block per PDF page. This function works on the
    raw page texts before chunking so that boilerplate never becomes a chunk.
    It combines pattern rules for known eCFR/OSHA/FDA print output with a
    frequency check for short lines repeated on most pages. Content lines are
    kept verbatim.
    """
    pages = [[line.strip() for line in text.splitlines() if line.strip()] for text in page_texts]
    repeated_keys: set[str] = set()
    if len(pages) >= 3:
        minimum_pages = max(3, (len(pages) * 3 + 4) // 5)
        counts: Counter[str] = Counter()
        for lines in pages:
            counts.update({_boilerplate_key(line) for line in lines})
        repeated_keys = {
            key for key, count in counts.items() if count >= minimum_pages and 0 < len(key) <= 240
        }

    cleaned: list[str] = []
    for lines in pages:
        kept = [
            line
            for line in lines
            if not _is_boilerplate_line(line) and _boilerplate_key(line) not in repeated_keys
        ]
        cleaned.append(_normalize_text("\n".join(kept)))
    return cleaned


def _boilerplate_key(line: str) -> str:
    key = re.sub(r"\s+", " ", line).strip().casefold()
    return re.sub(r"\d+", "#", key)


def _is_boilerplate_line(line: str) -> bool:
    normalized = re.sub(r"\s+", " ", line).strip()
    if not normalized:
        return True
    if normalized.casefold() in _BOILERPLATE_EXACT_LINES:
        return True
    return any(pattern.search(normalized) for pattern in _BOILERPLATE_LINE_PATTERNS)


def _extract_markdown(path: Path) -> ExtractedDocument:
    text = _read_text(path)
    blocks: list[TextBlock] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        content = _normalize_text("\n".join(current_lines))
        if content:
            blocks.append(
                TextBlock(
                    text=content,
                    page=None,
                    section_heading=current_heading,
                )
            )
        current_lines.clear()

    for line in text.splitlines():
        heading_match = _MARKDOWN_HEADING.match(line)
        if heading_match:
            flush()
            current_heading = heading_match.group(2).strip()
            current_lines.append(line.strip())
        else:
            current_lines.append(line)
    flush()

    if not blocks:
        raise ExtractionError("Document contains no extractable text.")
    return ExtractedDocument(blocks=tuple(blocks), page_count=None)


def _extract_text_file(path: Path) -> ExtractedDocument:
    text = _normalize_text(_read_text(path))
    if not text:
        raise ExtractionError("Document contains no extractable text.")
    return ExtractedDocument(
        blocks=(TextBlock(text=text, page=None, section_heading=None),),
        page_count=None,
    )


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ExtractionError("Text document is not valid UTF-8.") from exc
    except OSError as exc:
        raise ExtractionError("Document could not be read.") from exc


def _normalize_text(text: str) -> str:
    text = text.replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\x0c", "\n")
    text = "".join(
        character if character in {"\n", "\t"} or unicodedata.category(character)[0] != "C" else " "
        for character in text
    )
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
