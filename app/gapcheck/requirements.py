"""Deterministic extraction of normative requirements from regulation chunks."""

import re
from dataclasses import dataclass
from typing import Literal

from app.store.base import SearchHit

RequirementStrength = Literal["mandatory", "advisory"]

_MANDATORY = re.compile(
    r"\b(?:shall|must|is required to|are required to|will be required to)\b",
    re.I,
)
_ADVISORY = re.compile(r"\bshould\b", re.I)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\[])")
_WHITESPACE = re.compile(r"\s+")
_LIST_MARKER = re.compile(r"\(\s*(?:\d{1,2}|[a-z])\s*\)\s+", re.I)
_LIST_ITEM = re.compile(r"^\(\s*(?:\d{1,2}|[a-z])\s*\)\s+", re.I)
_OBLIGATION_INTRO = re.compile(
    r"\b(?:shall|must|is required to|are required to|will be required to|should)\b"
    r"[^.]*\b(?:includ(?:e|es|ed|ing)|contain(?:s|ed|ing)?|following)\b",
    re.I,
)
_DEFINITION = re.compile(r"\b(?:means|is defined as|are defined as)\b", re.I)


@dataclass(frozen=True)
class Requirement:
    requirement_id: str
    text: str
    strength: RequirementStrength
    chunk_id: str
    document_id: str
    title: str
    filename: str
    page: int | None
    snippet: str
    score: float


def extract_requirements(
    chunks: list[SearchHit],
    *,
    max_requirements: int = 120,
) -> tuple[list[Requirement], bool]:
    """Extract obligation sentences from chunks, deduplicated and capped.

    The return value is ``(requirements, capped)``. ``capped`` is true when
    more unique requirements were found than the configured hard cap.
    """
    requirements: list[Requirement] = []
    seen: set[str] = set()
    capped = False
    for chunk in chunks:
        for sentence, strength in _requirement_sentences(chunk.text):
            normalized = _dedupe_key(sentence)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            if len(requirements) >= max_requirements:
                capped = True
                break
            requirements.append(
                Requirement(
                    requirement_id=f"REQ-{len(requirements) + 1:03d}",
                    text=sentence,
                    strength=strength,
                    chunk_id=str(chunk.chunk_id),
                    document_id=str(chunk.document_id),
                    title=chunk.title,
                    filename=chunk.filename,
                    page=chunk.page,
                    snippet=sentence[:300],
                    score=chunk.score,
                )
            )
        if capped:
            break
    return requirements, capped


def _requirement_sentences(text: str) -> list[tuple[str, RequirementStrength]]:
    found: list[tuple[str, RequirementStrength]] = []
    pending: RequirementStrength | None = None
    for sentence in _sentences(text):
        intro_items = _intro_items(sentence)
        if intro_items is not None:
            intro_strength = _strength(sentence)
            if intro_strength is not None:
                pending = intro_strength
            for item in intro_items:
                _append_requirement(item, _strength(item) or pending, found)
            continue
        own = _strength(sentence)
        if own is not None:
            if _OBLIGATION_INTRO.search(sentence):
                pending = own
            _append_requirement(sentence, own, found)
            continue
        if _LIST_ITEM.match(sentence) and pending is not None:
            _append_requirement(sentence, pending, found)
    return found


def _intro_items(sentence: str) -> list[str] | None:
    if _OBLIGATION_INTRO.search(sentence) is None:
        return None
    marker = _LIST_MARKER.search(sentence)
    if marker is None:
        return None
    rest = sentence[marker.start() :]
    parts = re.split(f"(?={_LIST_MARKER.pattern})", rest)
    return [part.strip() for part in parts if part.strip()]


def _append_requirement(
    sentence: str,
    strength: RequirementStrength | None,
    found: list[tuple[str, RequirementStrength]],
) -> None:
    if strength is None or _DEFINITION.search(sentence):
        return
    found.append((sentence, strength))


def _sentences(text: str) -> list[str]:
    compact = _WHITESPACE.sub(" ", text).strip()
    if not compact:
        return []
    return [part.strip() for part in _SENTENCE_SPLIT.split(compact) if part.strip()]


def _strength(sentence: str) -> RequirementStrength | None:
    if _MANDATORY.search(sentence):
        return "mandatory"
    if _ADVISORY.search(sentence):
        return "advisory"
    return None


def _dedupe_key(sentence: str) -> str:
    return re.sub(r"\W+", " ", sentence).strip().casefold()
