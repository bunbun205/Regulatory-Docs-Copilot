import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

SUPPORTED_EXTENSIONS = {".pdf", ".md", ".markdown", ".txt"}
_MARKDOWN_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")


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
        blocks: list[TextBlock] = []
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                raw_text = page.extract_text() or ""
            except Exception as exc:
                raise ExtractionError(
                    f"Could not extract text from PDF page {page_number}."
                ) from exc
            text = _normalize_text(raw_text)
            if text:
                blocks.append(TextBlock(text=text, page=page_number, section_heading=None))
        page_count = len(reader.pages)
    except ExtractionError:
        raise
    except (PdfReadError, OSError, ValueError, TypeError) as exc:
        raise ExtractionError("PDF could not be read.") from exc

    if not blocks:
        raise ExtractionError("PDF contains no extractable text.")
    return ExtractedDocument(blocks=tuple(blocks), page_count=page_count)


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
