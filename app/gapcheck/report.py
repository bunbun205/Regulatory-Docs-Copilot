"""Deterministic finding severity and report assembly for gap checks."""

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from app.gapcheck.requirements import Requirement
from app.store.base import SearchHit

BANNER = (
    "Decision support only, not legal advice. This report is limited to the "
    "ingested corpus and does not establish legal compliance."
)

Direction = Literal["sop_to_regulation", "regulation_to_sop"]
Severity = Literal["high", "medium", "low"]

ALL_VERDICTS = (
    "compliant",
    "partial",
    "conflict",
    "not_covered_by_corpus",
    "judge_failed",
    "addressed",
    "partially_addressed",
    "missing",
)


@dataclass(frozen=True)
class RegulationCitation:
    chunk_id: str
    document_id: str
    title: str
    page: int | None
    snippet: str
    score: float | None


def citation_from_hit(hit: SearchHit, *, snippet_limit: int = 300) -> RegulationCitation:
    return RegulationCitation(
        chunk_id=str(hit.chunk_id),
        document_id=str(hit.document_id),
        title=hit.title,
        page=hit.page,
        snippet=_snippet(hit.text, snippet_limit),
        score=round(hit.score, 6),
    )


def citation_from_requirement(
    requirement: Requirement,
    *,
    snippet_limit: int = 300,
) -> RegulationCitation:
    return RegulationCitation(
        chunk_id=requirement.chunk_id,
        document_id=requirement.document_id,
        title=requirement.title,
        page=requirement.page,
        snippet=_snippet(requirement.snippet, snippet_limit),
        score=round(requirement.score, 6),
    )


def severity_for(verdict: str, strength: str | None) -> Severity:
    """Apply the documented rule; the LLM never chooses severity."""
    if verdict in {"conflict", "missing"} and strength != "advisory":
        return "high"
    if verdict in {"partial", "partially_addressed"} or strength == "advisory":
        return "medium"
    return "low"


def suggested_fix(verdict: str) -> str:
    if verdict in {"compliant", "addressed"}:
        suggestion = "No change suggested."
    elif verdict == "conflict":
        suggestion = (
            "Review the cited regulation and revise the SOP clause so it no longer "
            "contradicts the requirement."
        )
    elif verdict in {"partial", "partially_addressed"}:
        suggestion = "Add the missing detail from the cited regulation to the relevant SOP clause."
    elif verdict == "missing":
        suggestion = "Add an SOP clause that addresses the cited requirement."
    elif verdict == "not_covered_by_corpus":
        suggestion = (
            "Review whether the applicable regulation is in the ingested corpus; "
            "no conclusion is made from this run."
        )
    else:
        suggestion = "Manual review is required because the automated judgement failed."
    return f"Suggested fix (not legal advice): {suggestion}"


def make_finding(
    *,
    direction: Direction,
    verdict: str,
    sop_clause_refs: list[str] | tuple[str, ...],
    regulation_citations: list[RegulationCitation] | tuple[RegulationCitation, ...],
    rationale: str,
    requirement_strength: str | None = None,
    requirement_id: str | None = None,
) -> dict[str, Any]:
    return {
        "direction": direction,
        "verdict": verdict,
        "severity": severity_for(verdict, requirement_strength),
        "sop_clause_refs": list(sop_clause_refs),
        "regulation_citations": [
            {
                "chunk_id": citation.chunk_id,
                "document_id": citation.document_id,
                "title": citation.title,
                "page": citation.page,
                "snippet": citation.snippet,
                "score": citation.score,
            }
            for citation in regulation_citations
        ],
        "rationale": _snippet(rationale, 1000),
        "suggested_fix": suggested_fix(verdict),
        "requirement_strength": requirement_strength,
        "requirement_id": requirement_id,
    }


def build_report(
    *,
    job_id: str,
    sop_clauses: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    metadata: dict[str, Any],
    caps_hit: list[str],
    generated_at: datetime,
) -> dict[str, Any]:
    numbered_findings = [
        {"finding_id": f"GAP-{index:04d}", **finding}
        for index, finding in enumerate(findings, start=1)
    ]
    verdict_counts = Counter(finding["verdict"] for finding in numbered_findings)
    severity_counts = Counter(finding["severity"] for finding in numbered_findings)
    direction_counts = Counter(finding["direction"] for finding in numbered_findings)
    return {
        "job_id": job_id,
        "generated_at": generated_at.isoformat(),
        "banner": BANNER,
        "metadata": metadata,
        "caps_hit": sorted(caps_hit),
        "counts_by_verdict": {verdict: verdict_counts.get(verdict, 0) for verdict in ALL_VERDICTS},
        "counts_by_severity": {
            severity: severity_counts.get(severity, 0) for severity in ("high", "medium", "low")
        },
        "counts_by_direction": {
            direction: direction_counts.get(direction, 0)
            for direction in ("sop_to_regulation", "regulation_to_sop")
        },
        "sop_clauses": sop_clauses,
        "findings": numbered_findings,
    }


def _snippet(text: str, limit: int) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    return normalized[:limit]
