"""Explicit denominators; unknown or unreviewed results are never perfect scores."""

import re
from itertools import combinations
from typing import Any

import numpy as np

from eval.datasets import CleanReview, Defect, SourceLocation, report_hash

DEFECT_VERDICTS = {"partial", "conflict", "missing", "partially_addressed"}
DETERMINATE_VERDICTS = DEFECT_VERDICTS | {"compliant", "addressed"}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def matches(source: SourceLocation, hit: dict[str, Any]) -> bool:
    return (
        source.filename == hit.get("filename")
        and source.content_sha256 == hit.get("content_sha256")
        and (source.page is None or source.page == hit.get("page"))
        and (
            not source.section
            or normalize(source.section)
            in normalize(str(hit.get("section_heading") or "") + " " + hit.get("text", ""))
        )
        and normalize(source.quote) in normalize(hit.get("text", ""))
    )


def retrieval_metrics(sources: list[SourceLocation], hits: list[dict]) -> dict[str, float | int]:
    ranks = [next((i for i, hit in enumerate(hits, 1) if matches(s, hit)), 0) for s in sources]
    found = [rank for rank in ranks if rank]
    return {
        "targets": len(sources),
        "targets_found": len(found),
        "recall_at_k": len(found) / len(sources) if sources else 0.0,
        "reciprocal_rank": 1 / min(found) if found else 0.0,
        "all_sources_found": int(bool(sources) and len(found) == len(sources)),
    }


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def percentiles(values: list[float]) -> dict[str, float | int | None]:
    return {
        "samples": len(values),
        "p50_ms": float(np.percentile(values, 50)) if values else None,
        "p95_ms": float(np.percentile(values, 95)) if values else None,
    }


def raw_citations(payload: dict | None, allowed: set[str]) -> tuple[int, int]:
    """Count proposed references before the application's validator strips any."""
    if payload is None or not isinstance(payload.get("citations"), list):
        return 0, 0
    citations = payload["citations"]
    return sum(isinstance(c, str) and c.strip() in allowed for c in citations), len(citations)


def question_summary(rows: list[dict]) -> dict[str, Any]:
    scored = [r for r in rows if r["verified"]]
    answerable = [r for r in scored if r["kind"] != "unanswerable"]
    unanswerable = [r for r in scored if r["kind"] == "unanswerable" and r["generation_enabled"]]
    proposed = sum(r.get("proposed_citations", 0) for r in scored)
    valid = sum(r.get("valid_citations", 0) for r in scored)
    generated_answerable = [r for r in answerable if r["generation_enabled"]]
    return {
        "verified_questions": len(scored),
        "answerable_questions": len(answerable),
        "retrieval_recall_at_k": (
            sum(r.get("recall_at_k", 0) for r in answerable) / len(answerable)
            if answerable
            else None
        ),
        "retrieval_mrr": (
            sum(r.get("reciprocal_rank", 0) for r in answerable) / len(answerable)
            if answerable
            else None
        ),
        "raw_citation_validity": ratio(valid, proposed),
        "valid_citations": valid,
        "proposed_citations": proposed,
        "citation_valid_answer_rate": ratio(
            sum(r.get("grounded", False) for r in generated_answerable), len(generated_answerable)
        ),
        "abstention_accuracy": ratio(
            sum(r.get("abstained", False) for r in unanswerable), len(unanswerable)
        ),
        "unanswerable_questions": len(unanswerable),
        "failed_questions": sum(bool(r.get("error")) for r in scored),
        "retrieval_latency": percentiles([r["retrieve_ms"] for r in scored if "retrieve_ms" in r]),
        "total_latency": percentiles([r["total_ms"] for r in scored]),
    }


def defect_detected(defect: Defect, report: dict, chunks: dict[str, dict]) -> bool:
    clauses = {c["clause_id"]: c["text"] for c in report["sop_clauses"]}
    for finding in report["findings"]:
        if finding["direction"] != defect.direction or finding["verdict"] not in defect.verdicts:
            continue
        if defect.sop_quote and not any(
            normalize(defect.sop_quote) in normalize(clauses.get(ref, ""))
            for ref in finding["sop_clause_refs"]
        ):
            continue
        if any(
            matches(defect.source, chunks.get(c["chunk_id"], {}))
            and citation_valid(c, chunks)
            and (
                not defect.requirement_quote
                or normalize(defect.requirement_quote) in normalize(c["snippet"])
            )
            for c in finding["regulation_citations"]
        ):
            return True
    return False


def citation_valid(citation: dict, chunks: dict[str, dict]) -> bool:
    hit = chunks.get(citation["chunk_id"])
    return bool(
        hit
        and citation["document_id"] == hit["document_id"]
        and citation["page"] == hit["page"]
        and normalize(citation["snippet"])
        and normalize(citation["snippet"]) in normalize(hit["text"])
    )


def gap_citations(report: dict, chunks: dict[str, dict]) -> tuple[int, int]:
    clauses = {c["clause_id"] for c in report["sop_clauses"]}
    valid = total = 0
    for finding in report["findings"]:
        for citation in finding["regulation_citations"]:
            total += 1
            valid += citation_valid(citation, chunks)
        for ref in finding["sop_clause_refs"]:
            total += 1
            valid += ref in clauses
    return valid, total


def clean_false_positives(report: dict, reviews: list[CleanReview]) -> tuple[int, int] | None:
    review = next((r for r in reviews if r.report_sha256 == report_hash(report)), None)
    if review is None:
        return None
    eligible = [f for f in report["findings"] if f["verdict"] in DETERMINATE_VERDICTS]
    positives = {f["finding_id"] for f in eligible if f["verdict"] in DEFECT_VERDICTS}
    if not set(review.false_positive_ids) <= positives or len(
        set(review.false_positive_ids)
    ) != len(review.false_positive_ids):
        raise ValueError("Clean review contains duplicate or nonexistent defect finding IDs.")
    return len(review.false_positive_ids), len(eligible)


def stability(reports: list[dict]) -> dict[str, float | int | None]:
    signatures = []
    for report in reports:
        signatures.append(
            {
                (
                    f["direction"],
                    f["verdict"],
                    tuple(sorted(f["sop_clause_refs"])),
                    tuple(
                        sorted(
                            (c["chunk_id"], normalize(c["snippet"]))
                            for c in f["regulation_citations"]
                        )
                    ),
                )
                for f in report["findings"]
            }
        )
    comparisons = [len(a & b) / len(a | b) for a, b in combinations(signatures, 2) if a | b]
    return {
        "comparisons": len(comparisons),
        "verdict_set_jaccard": float(np.mean(comparisons)) if comparisons else None,
    }
