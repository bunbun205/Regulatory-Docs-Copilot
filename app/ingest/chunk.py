import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from app.ingest.extract import TextBlock

_TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
_WORD_SPLIT = re.compile(r"\S+")


def estimate_tokens(text: str) -> int:
    """Approximate BGE-style subword tokens without loading the tokenizer.

    This is deliberately deterministic and cheap. It counts word-like runs and
    individual punctuation marks; the ingestion report labels token counts as
    approximate for that reason.
    """
    return len(_TOKEN_PATTERN.findall(text))


@dataclass(frozen=True)
class ChunkDraft:
    text: str
    token_count: int
    page: int | None
    section_heading: str | None


@dataclass(frozen=True)
class _Unit:
    text: str
    separator: str
    token_count: int


def make_chunks(
    blocks: Iterable[TextBlock],
    *,
    max_tokens: int = 500,
    overlap_tokens: int = 80,
    count_tokens: Callable[[str], int] = estimate_tokens,
) -> list[ChunkDraft]:
    """Recursively split blocks into overlapping chunks.

    Splitting proceeds paragraph -> sentence -> word -> character, so the
    resulting chunks stay under ``max_tokens`` and preserve page/section
    metadata from the source block.
    """
    if max_tokens <= 0:
        raise ValueError("max_tokens must be positive")
    if overlap_tokens < 0 or overlap_tokens >= max_tokens:
        raise ValueError("overlap_tokens must be non-negative and less than max_tokens")

    chunks: list[ChunkDraft] = []
    for block in blocks:
        text = block.text.strip()
        if not text:
            continue
        for piece in _split_text(
            text,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
            count_tokens=count_tokens,
        ):
            token_count = count_tokens(piece)
            if token_count == 0:
                continue
            chunks.append(
                ChunkDraft(
                    text=piece,
                    token_count=token_count,
                    page=block.page,
                    section_heading=block.section_heading,
                )
            )
    return chunks


def _split_text(
    text: str,
    *,
    max_tokens: int,
    overlap_tokens: int,
    count_tokens: Callable[[str], int],
) -> list[str]:
    if count_tokens(text) <= max_tokens:
        return [text]

    units = _build_units(text, max_tokens=max_tokens, count_tokens=count_tokens)
    pieces: list[str] = []
    start = 0
    while start < len(units):
        end = start
        tokens = 0
        while end < len(units) and tokens + units[end].token_count <= max_tokens:
            tokens += units[end].token_count
            end += 1
        if end == start:
            end = start + 1

        piece = "".join(unit.separator + unit.text for unit in units[start:end]).strip()
        if piece:
            pieces.append(piece)

        if end == len(units):
            break

        overlap_start = end
        overlap = 0
        while overlap_start > start:
            candidate = units[overlap_start - 1]
            if overlap + candidate.token_count > overlap_tokens:
                break
            overlap += candidate.token_count
            overlap_start -= 1

        start = end if overlap_start == start else overlap_start

    return pieces


def _build_units(
    text: str,
    *,
    max_tokens: int,
    count_tokens: Callable[[str], int],
) -> list[_Unit]:
    units: list[_Unit] = []
    paragraphs = [paragraph.strip() for paragraph in _PARAGRAPH_SPLIT.split(text)]
    for paragraph in paragraphs:
        if not paragraph:
            continue
        separator = "" if not units else "\n\n"
        units.extend(
            _paragraph_units(
                paragraph,
                separator=separator,
                max_tokens=max_tokens,
                count_tokens=count_tokens,
            )
        )
    return units


def _paragraph_units(
    paragraph: str,
    *,
    separator: str,
    max_tokens: int,
    count_tokens: Callable[[str], int],
) -> list[_Unit]:
    paragraph_tokens = count_tokens(paragraph)
    if paragraph_tokens <= max_tokens:
        return [_Unit(paragraph, separator, paragraph_tokens)]

    units: list[_Unit] = []
    first_sentence = True
    for raw_sentence in _SENTENCE_SPLIT.split(paragraph):
        sentence = raw_sentence.strip()
        if not sentence:
            continue
        sentence_separator = separator if first_sentence else " "
        first_sentence = False
        sentence_tokens = count_tokens(sentence)
        if sentence_tokens <= max_tokens:
            units.append(_Unit(sentence, sentence_separator, sentence_tokens))
        else:
            units.extend(
                _word_units(
                    sentence,
                    separator=sentence_separator,
                    max_tokens=max_tokens,
                    count_tokens=count_tokens,
                )
            )
    return units


def _word_units(
    text: str,
    *,
    separator: str,
    max_tokens: int,
    count_tokens: Callable[[str], int],
) -> list[_Unit]:
    units: list[_Unit] = []
    current_words: list[str] = []
    current_tokens = 0
    next_separator = separator

    def flush() -> None:
        nonlocal current_words, current_tokens, next_separator
        if current_words:
            units.append(_Unit(" ".join(current_words), next_separator, current_tokens))
            current_words = []
            current_tokens = 0
            next_separator = " "

    for word in _WORD_SPLIT.findall(text):
        word_tokens = count_tokens(word)
        if word_tokens > max_tokens:
            flush()
            for piece in _character_units(word, max_tokens=max_tokens, count_tokens=count_tokens):
                units.append(_Unit(piece, next_separator, count_tokens(piece)))
                next_separator = " "
            continue
        if current_words and current_tokens + word_tokens > max_tokens:
            flush()
        current_words.append(word)
        current_tokens += word_tokens
    flush()
    return units


def _character_units(
    text: str,
    *,
    max_tokens: int,
    count_tokens: Callable[[str], int],
) -> list[str]:
    pieces: list[str] = []
    remaining = text
    while remaining:
        low, high = 1, len(remaining)
        best = 1
        while low <= high:
            middle = (low + high) // 2
            if count_tokens(remaining[:middle]) <= max_tokens:
                best = middle
                low = middle + 1
            else:
                high = middle - 1
        pieces.append(remaining[:best])
        remaining = remaining[best:]
    return pieces
