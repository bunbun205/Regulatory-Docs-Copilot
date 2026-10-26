"""Evaluate the existing application pipelines without changing their decisions."""

import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import Settings
from app.gapcheck.jobs import config_from_settings
from app.gapcheck.judge import GapCheckJudge
from app.gapcheck.runner import GapCheckRunner
from app.ingest.embedding import Embedder
from app.ingest.extract import extract_document
from app.llm.base import LLMClient, LLMResult
from app.rag.answerer import Answerer
from app.rag.grounding import parse_answer_payload
from app.rag.retriever import Backend, RetrievalResult, Retriever
from app.store.base import SearchFilters
from eval.datasets import CleanReview, GapCase, Question, file_hash, report_hash
from eval.metrics import (
    clean_false_positives,
    defect_detected,
    gap_citations,
    matches,
    percentiles,
    question_summary,
    ratio,
    raw_citations,
    retrieval_metrics,
    stability,
)


def corpus_snapshot(chunks: dict[str, dict]) -> str:
    sources = sorted({(c["filename"], c["content_sha256"]) for c in chunks.values()})
    return hashlib.sha256(json.dumps(sources).encode()).hexdigest()


def validate_labels(
    questions: list[Question], cases: list[GapCase], chunks: dict[str, dict]
) -> None:
    snapshot = corpus_snapshot(chunks)
    by_id = {c.id: c for c in cases}
    for entry in [q for q in questions if q.verified] + [c for c in cases if c.verified]:
        if entry.corpus_snapshot and entry.corpus_snapshot != snapshot:
            raise ValueError(
                f"{entry.id}: reviewed corpus snapshot does not match the loaded corpus."
            )
        sources = (
            entry.expected_sources
            if isinstance(entry, Question)
            else [d.source for d in entry.defects]
        )
        for source in sources:
            if not any(matches(source, chunk) for chunk in chunks.values()):
                raise ValueError(
                    f"{entry.id}: reviewed source location/hash/quote is absent from the corpus."
                )
        if isinstance(entry, GapCase) and entry.kind == "mutation":
            baseline = by_id.get(entry.baseline_id or "")
            if baseline is None or not baseline.verified or baseline.kind != "clean":
                raise ValueError(
                    f"{entry.id}: verified mutation requires a verified clean baseline."
                )


class ReplayRetriever:
    """Reuse the measured retrieval so generation is evaluated against those hits."""

    def __init__(self, result: RetrievalResult) -> None:
        self.result = result

    async def retrieve(self, *args: Any, **kwargs: Any) -> RetrievalResult:
        return self.result


class RecordingLLM:
    def __init__(self, client: LLMClient) -> None:
        self.client = client
        self.result: LLMResult | None = None

    async def chat(self, *args: Any, **kwargs: Any) -> LLMResult:
        self.result = await self.client.chat(*args, **kwargs)
        return self.result

    async def close(self) -> None:
        return None  # The runner owns the underlying shared client.


async def evaluate_questions(
    questions: list[Question],
    retriever: Retriever,
    chunks: dict[str, dict],
    backend: Backend,
    config: Settings,
    llm: LLMClient | None,
    *,
    top_k: int,
    diagnostic_unverified: bool = False,
) -> dict[str, Any]:
    rows = []
    for question in questions:
        if not question.verified and not diagnostic_unverified:
            continue
        started = time.perf_counter()
        row: dict[str, Any] = {
            "id": question.id,
            "kind": question.kind,
            "verified": question.verified,
            "generation_enabled": llm is not None and question.verified,
        }
        try:
            result = await retriever.retrieve(question.question, top_k=top_k, backend=backend)
            hits = []
            for hit in result.hits:
                source = chunks.get(str(hit.chunk_id))
                # Refuse stale Qdrant records instead of silently scoring a different corpus.
                if (
                    source is None
                    or hit.text != source["text"]
                    or str(hit.document_id) != source["document_id"]
                ):
                    raise ValueError("Retrieved chunk does not match the Postgres corpus snapshot.")
                hits.append({**asdict(hit), "content_sha256": source["content_sha256"]})
            row.update(
                retrieve_ms=result.latency_ms,
                retrieved_chunk_ids=[str(h.chunk_id) for h in result.hits],
            )
            if question.verified and question.kind != "unanswerable":
                row.update(retrieval_metrics(question.expected_sources, hits))
            if llm is not None and question.verified:
                recorder = RecordingLLM(llm)
                answerer = Answerer(
                    ReplayRetriever(result),  # type: ignore[arg-type]
                    recorder,
                    abstention_threshold=config.ABSTENTION_THRESHOLD,
                    top_k=top_k,
                    temperature=config.LLM_TEMPERATURE,
                    max_tokens=config.LLM_MAX_TOKENS,
                )
                answer = await answerer.answer(question.question, backend=backend)
                valid, proposed = raw_citations(
                    parse_answer_payload(recorder.result.text) if recorder.result else None,
                    {str(h.chunk_id) for h in result.hits},
                )
                row.update(
                    abstained=answer.insufficient_evidence,
                    grounded=answer.grounded,
                    grounding_reason=answer.grounding_reason,
                    valid_citations=valid,
                    proposed_citations=proposed,
                    generate_ms=answer.generate_latency_ms,
                    token_usage=asdict(answer.usage),
                )
        except Exception as exc:
            # Keep failed verified questions in quality denominators. Do not log
            # provider details, request headers or private source text.
            row["error"] = type(exc).__name__
        row["total_ms"] = round((time.perf_counter() - started) * 1000, 3)
        rows.append(row)
    return {
        "summary": question_summary(rows),
        "unverified_excluded": sum(not q.verified for q in questions),
        "diagnostic_unverified_queries": sum(not r["verified"] for r in rows),
        "diagnostics": {
            "failed_queries": sum(bool(r.get("error")) for r in rows if not r["verified"]),
            "retrieval_latency": percentiles(
                [r["retrieve_ms"] for r in rows if not r["verified"] and "retrieve_ms" in r]
            ),
        },
        "rows": rows,
    }


async def evaluate_gaps(
    cases: list[GapCase],
    dataset_dir: Path,
    retriever: Retriever,
    embedder: Embedder,
    llm: LLMClient | None,
    chunks: dict[str, dict],
    backend: Backend,
    config: Settings,
    repeats: int,
    clean_reviews: list[CleanReview],
    review_dir: Path,
) -> dict[str, Any]:
    rows = []
    valid = references = detected = expected = false_positives = clean_opportunities = 0
    reviewed_runs = 0
    for case in cases:
        if not case.verified:
            continue
        reports = []
        case_rows = []
        sop_file = (dataset_dir / case.sop_path).resolve()
        if file_hash(sop_file) != case.sop_sha256:
            raise ValueError(f"{case.id}: SOP changed since author verification.")
        sop = "\n\n".join(block.text for block in extract_document(sop_file).blocks)
        for repeat in range(repeats):
            row: dict[str, Any] = {"repeat": repeat + 1, "defects_expected": len(case.defects)}
            expected += len(case.defects)
            try:
                if llm is None:
                    raise ValueError("Gap evaluation requires generation.")
                # Fresh judge without persistent cache for every repeat.
                judge = GapCheckJudge(
                    llm,
                    namespace=f"eval:{config.LLM_PROVIDER}:{config.LLM_MODEL}",
                    max_tokens=config.GAPCHECK_JUDGE_MAX_TOKENS,
                )
                runner = GapCheckRunner(
                    retriever,
                    embedder,
                    judge,
                    config_from_settings(config),
                    job_id=str(uuid4()),
                    model_label=f"{config.LLM_PROVIDER}:{config.LLM_MODEL}",
                )
                report = await runner.run(
                    sop, backend=backend, filters=SearchFilters(**case.filters)
                )
                reports.append(report)
                found = [d.id for d in case.defects if defect_detected(d, report, chunks)]
                detected += len(found)
                good, total = gap_citations(report, chunks)
                valid += good
                references += total
                digest = report_hash(report)
                review_dir.mkdir(parents=True, exist_ok=True)
                # Local-only evidence may contain private SOPs. Never commit it by default.
                (review_dir / f"{digest}.json").write_text(json.dumps(report, indent=2) + "\n")
                row.update(
                    report_sha256=digest,
                    defects_detected=found,
                    valid_references=good,
                    references=total,
                    judge_failed=report["metadata"]["judge_failures"],
                    caps_hit=report["caps_hit"],
                    duration_ms=report["metadata"]["duration_ms"],
                )
                if case.kind == "clean":
                    reviewed = clean_false_positives(report, clean_reviews)
                    if reviewed is not None:
                        false_positives += reviewed[0]
                        clean_opportunities += reviewed[1]
                        reviewed_runs += 1
            except Exception as exc:
                row["error"] = type(exc).__name__
            case_rows.append(row)
        rows.append(
            {"id": case.id, "kind": case.kind, "runs": case_rows, "stability": stability(reports)}
        )
    return {
        "verified_cases": sum(c.verified for c in cases),
        "unverified_excluded": sum(not c.verified for c in cases),
        "defects_detected": detected,
        "defects_expected_across_repeats": expected,
        "injected_defect_recall": ratio(detected, expected),
        "valid_references": valid,
        "references": references,
        "citation_validity": ratio(valid, references),
        "clean_reviewed_runs": reviewed_runs,
        "clean_reviewed_determinate_findings": clean_opportunities,
        "clean_false_positives": false_positives,
        "clean_false_positive_rate": ratio(false_positives, clean_opportunities),
        "failed_runs": sum(bool(r.get("error")) for c in rows for r in c["runs"]),
        "rows": rows,
    }
