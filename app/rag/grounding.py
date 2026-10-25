import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.store.base import SearchHit

_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)
_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class GroundedAnswer:
    answer: str
    citations: tuple[SearchHit, ...]
    grounded: bool
    reason: str | None


def parse_answer_payload(text: str) -> dict[str, Any] | None:
    candidate = text.strip()
    fence = _FENCE.match(candidate)
    if fence:
        candidate = fence.group(1).strip()
    try:
        payload = json.loads(candidate)
    except ValueError:
        match = _JSON_OBJECT.search(candidate)
        if match is None:
            return None
        try:
            payload = json.loads(match.group(0))
        except ValueError:
            return None
    return payload if isinstance(payload, dict) else None


def validate_answer(text: str, hits: Sequence[SearchHit]) -> GroundedAnswer:
    payload = parse_answer_payload(text)
    if payload is None:
        return GroundedAnswer(
            answer=text.strip() or "The model returned no answer.",
            citations=(),
            grounded=False,
            reason="invalid_json",
        )

    raw_answer = payload.get("answer")
    raw_citations = payload.get("citations")
    answer = raw_answer.strip() if isinstance(raw_answer, str) else ""
    if not answer:
        return GroundedAnswer(
            answer="The model returned no answer.",
            citations=(),
            grounded=False,
            reason="empty_answer",
        )
    if not isinstance(raw_citations, list):
        return GroundedAnswer(
            answer=answer,
            citations=(),
            grounded=False,
            reason="invalid_citations",
        )

    by_id = {str(hit.chunk_id): hit for hit in hits}
    citations: list[SearchHit] = []
    seen: set[str] = set()
    invalid = 0
    for value in raw_citations:
        if not isinstance(value, str):
            invalid += 1
            continue
        key = value.strip()
        hit = by_id.get(key)
        if hit is None:
            invalid += 1
            continue
        if key not in seen:
            seen.add(key)
            citations.append(hit)

    if not citations:
        return GroundedAnswer(
            answer=answer,
            citations=(),
            grounded=False,
            reason="no_valid_citations",
        )
    if invalid:
        return GroundedAnswer(
            answer=answer,
            citations=tuple(citations),
            grounded=False,
            reason="invalid_citations_removed",
        )
    return GroundedAnswer(
        answer=answer,
        citations=tuple(citations),
        grounded=True,
        reason=None,
    )


def citation_snippet(text: str, limit: int = 300) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    return normalized[:limit]
