"""Orchestration for the two-direction compliance gap checker."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, cast

import numpy as np
import structlog

from app.gapcheck.judge import (
    ClauseJudgement,
    GapCheckJudge,
    JudgeFailure,
    RequirementJudgement,
)
from app.gapcheck.report import (
    build_report,
    citation_from_hit,
    citation_from_requirement,
    make_finding,
)
from app.gapcheck.requirements import Requirement, extract_requirements
from app.gapcheck.segment import segment_sop
from app.ingest.embedding import Embedder
from app.llm.base import TokenUsage
from app.llm.budget import TokenBudget
from app.rag.retriever import Backend, RetrievalError, Retriever
from app.store.base import SearchFilters, SearchHit

logger = structlog.get_logger("labdocs.gapcheck.runner")

ProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]
CancelCheck = Callable[[], Awaitable[bool]]


class GapCheckCancelled(Exception):
    """The job owner requested cooperative cancellation."""


class GapCheckError(Exception):
    """A safe, user-facing gap-check failure."""


@dataclass(frozen=True)
class GapCheckConfig:
    max_clauses: int = 80
    max_requirements: int = 120
    max_tokens: int = 200_000
    retrieval_top_k: int = 5
    relevance_threshold: float = 0.60
    global_top_documents: int = 2
    sop_match_top_k: int = 3
    judge_concurrency: int = 4
    retrieval_concurrency: int = 8
    judge_max_tokens: int = 512


class GapCheckRunner:
    def __init__(
        self,
        retriever: Retriever,
        embedder: Embedder,
        judge: GapCheckJudge,
        config: GapCheckConfig,
        *,
        job_id: str,
        model_label: str,
        progress_callback: ProgressCallback | None = None,
        cancel_check: CancelCheck | None = None,
    ) -> None:
        self.retriever = retriever
        self.embedder = embedder
        self.judge = judge
        self.config = config
        self.job_id = job_id
        self.model_label = model_label
        self.progress_callback = progress_callback
        self.cancel_check = cancel_check
        self._usage = TokenUsage()
        self._cache_hits = 0
        self._judge_failures = 0
        self._caps_hit: set[str] = set()
        self._budget = TokenBudget(config.max_tokens)
        self.judge.budget = self._budget

    async def run(
        self,
        sop_text: str,
        *,
        filters: SearchFilters | None = None,
        backend: Backend = "pgvector",
    ) -> dict[str, Any]:
        started = time.perf_counter()
        clauses_frame = segment_sop(sop_text, max_clauses=self.config.max_clauses)
        clauses = cast(list[dict[str, Any]], clauses_frame.to_dict(orient="records"))
        clauses_total = len(clauses)
        await self._progress(
            phase="clauses",
            clauses_total=clauses_total,
            clauses_done=0,
            requirements_total=0,
            requirements_done=0,
        )

        unique_chunks: dict[str, SearchHit] = {}
        chunk_lock = asyncio.Lock()
        progress_lock = asyncio.Lock()
        retrieval_sem = asyncio.Semaphore(max(1, self.config.retrieval_concurrency))
        judge_sem = asyncio.Semaphore(max(1, self.config.judge_concurrency))
        clauses_done = 0

        async def analyze_clause(clause: dict[str, Any]) -> dict[str, Any]:
            nonlocal clauses_done
            await self._check_cancel()
            async with retrieval_sem:
                result = await self.retriever.retrieve(
                    str(clause["text"]),
                    top_k=self.config.retrieval_top_k,
                    filters=filters or SearchFilters(),
                    backend=backend,
                )
            relevant = [hit for hit in result.hits if hit.score >= self.config.relevance_threshold]
            if not relevant:
                finding = make_finding(
                    direction="sop_to_regulation",
                    verdict="not_covered_by_corpus",
                    sop_clause_refs=[str(clause["clause_id"])],
                    regulation_citations=[],
                    rationale=(
                        "No retrieved regulation chunk met the relevance threshold "
                        f"({self.config.relevance_threshold:.2f}); no LLM judgement was made."
                    ),
                )
            else:
                async with chunk_lock:
                    for hit in relevant:
                        unique_chunks.setdefault(str(hit.chunk_id), hit)
                judgement, failure = await self._judge_clause(
                    judge_sem,
                    clause_id=str(clause["clause_id"]),
                    clause_text=str(clause["text"]),
                    section=str(clause["section"]),
                    retrieved_hits=relevant,
                )
                if judgement is None:
                    finding = make_finding(
                        direction="sop_to_regulation",
                        verdict="judge_failed",
                        sop_clause_refs=[str(clause["clause_id"])],
                        regulation_citations=[],
                        rationale=_failure_rationale(failure),
                    )
                else:
                    by_id = {str(hit.chunk_id): hit for hit in relevant}
                    finding = make_finding(
                        direction="sop_to_regulation",
                        verdict=judgement.verdict,
                        sop_clause_refs=[str(clause["clause_id"])],
                        regulation_citations=[
                            citation_from_hit(by_id[citation])
                            for citation in judgement.citations
                            if citation in by_id
                        ],
                        rationale=judgement.rationale,
                    )
            async with progress_lock:
                clauses_done += 1
                await self._progress(
                    phase="clauses",
                    clauses_total=clauses_total,
                    clauses_done=clauses_done,
                    requirements_total=0,
                    requirements_done=0,
                )
            return finding

        clause_results = await asyncio.gather(
            *(analyze_clause(clause) for clause in clauses),
            return_exceptions=True,
        )
        findings: list[dict[str, Any]] = []
        for result in clause_results:
            if isinstance(result, GapCheckCancelled):
                raise result
            if isinstance(result, Exception):
                raise result
            findings.append(cast(dict[str, Any], result))

        chunks = sorted(unique_chunks.values(), key=lambda hit: hit.score, reverse=True)
        global_document_ids: list[str] = []
        if chunks:
            await self._check_cancel()
            scope_query = sop_text[:4000]
            try:
                global_result = await self.retriever.retrieve(
                    scope_query,
                    top_k=max(10, self.config.retrieval_top_k * 2),
                    filters=filters or SearchFilters(),
                    backend=backend,
                )
            except RetrievalError:
                logger.warning("gapcheck.global_retrieval_failed", job_id=self.job_id)
                global_result = None
            if global_result is not None:
                document_scores: dict[str, float] = {}
                for hit in global_result.hits:
                    if hit.score < self.config.relevance_threshold:
                        continue
                    document_id = str(hit.document_id)
                    document_scores[document_id] = max(
                        document_scores.get(document_id, -1.0),
                        hit.score,
                    )
                global_document_ids = [
                    document_id
                    for document_id, _ in sorted(
                        document_scores.items(),
                        key=lambda item: item[1],
                        reverse=True,
                    )[: self.config.global_top_documents]
                ]
                if global_document_ids:
                    allowed_documents = set(global_document_ids)
                    chunks = [hit for hit in chunks if str(hit.document_id) in allowed_documents]
        requirements, requirements_capped = extract_requirements(
            chunks,
            max_requirements=self.config.max_requirements,
        )
        if requirements_capped:
            self._caps_hit.add("requirements")
        requirements_total = len(requirements)
        await self._progress(
            phase="requirements",
            clauses_total=clauses_total,
            clauses_done=clauses_done,
            requirements_total=requirements_total,
            requirements_done=0,
        )

        if requirements:
            findings.extend(
                await self._analyze_requirements(
                    requirements=requirements,
                    clauses=clauses,
                    judge_sem=judge_sem,
                    progress_lock=progress_lock,
                    clauses_done=clauses_done,
                    clauses_total=clauses_total,
                )
            )

        await self._progress(
            phase="finalizing",
            clauses_total=clauses_total,
            clauses_done=clauses_done,
            requirements_total=requirements_total,
            requirements_done=requirements_total,
        )
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        judge_failed_count = sum(1 for finding in findings if finding["verdict"] == "judge_failed")
        if self._budget.cap_hit:
            self._caps_hit.add("tokens")
        if self._budget.attempts:
            self._usage = self._budget.usage
        metadata = {
            "model": self.model_label,
            "backend": backend,
            "filters": asdict(filters or SearchFilters()),
            "duration_ms": duration_ms,
            "token_usage": {
                "input_tokens": self._usage.input_tokens,
                "output_tokens": self._usage.output_tokens,
                "total_tokens": self._usage.total_tokens,
            },
            "token_budget": self._budget.summary(),
            "clauses_total": clauses_total,
            "requirements_total": requirements_total,
            "retrieval_top_k": self.config.retrieval_top_k,
            "relevance_threshold": self.config.relevance_threshold,
            "global_top_documents": self.config.global_top_documents,
            "requirement_document_ids": global_document_ids,
            "sop_match_top_k": self.config.sop_match_top_k,
            "judge_concurrency": self.config.judge_concurrency,
            "judge_cache_hits": self._cache_hits,
            "judge_failures": judge_failed_count,
            "caps": {
                "max_clauses": self.config.max_clauses,
                "max_requirements": self.config.max_requirements,
                "max_tokens": self.config.max_tokens,
                "requirements_capped": requirements_capped,
            },
        }
        return build_report(
            job_id=self.job_id,
            sop_clauses=clauses,
            findings=findings,
            metadata=metadata,
            caps_hit=sorted(self._caps_hit),
            generated_at=datetime.now(UTC),
        )

    async def _analyze_requirements(
        self,
        *,
        requirements: list[Requirement],
        clauses: list[dict[str, Any]],
        judge_sem: asyncio.Semaphore,
        progress_lock: asyncio.Lock,
        clauses_done: int,
        clauses_total: int,
    ) -> list[dict[str, Any]]:
        clause_vectors = await asyncio.to_thread(
            self.embedder.embed,
            [str(clause["text"]) for clause in clauses],
        )
        requirement_vectors = await asyncio.to_thread(
            self.embedder.embed,
            [requirement.text for requirement in requirements],
        )
        if clause_vectors.shape != (len(clauses), self.embedder.dimension):
            raise GapCheckError("The embedding service returned an invalid SOP index.")
        if requirement_vectors.shape != (len(requirements), self.embedder.dimension):
            raise GapCheckError("The embedding service returned invalid requirement vectors.")
        similarity = clause_vectors @ requirement_vectors.T
        requirements_done = 0

        async def analyze_requirement(
            index: int,
            requirement: Requirement,
        ) -> dict[str, Any]:
            nonlocal requirements_done
            await self._check_cancel()
            order = np.argsort(-similarity[:, index])[: self.config.sop_match_top_k]
            candidates = [
                {
                    "clause_id": str(clauses[int(clause_index)]["clause_id"]),
                    "section": str(clauses[int(clause_index)]["section"]),
                    "text": str(clauses[int(clause_index)]["text"]),
                }
                for clause_index in order
            ]
            judgement, failure = await self._judge_requirement(
                judge_sem,
                requirement=requirement,
                candidate_clauses=candidates,
            )
            if judgement is None:
                finding = make_finding(
                    direction="regulation_to_sop",
                    verdict="judge_failed",
                    sop_clause_refs=[],
                    regulation_citations=[citation_from_requirement(requirement)],
                    rationale=_failure_rationale(failure),
                    requirement_strength=requirement.strength,
                    requirement_id=requirement.requirement_id,
                )
            else:
                finding = make_finding(
                    direction="regulation_to_sop",
                    verdict=judgement.verdict,
                    sop_clause_refs=list(judgement.citations),
                    regulation_citations=[citation_from_requirement(requirement)],
                    rationale=judgement.rationale,
                    requirement_strength=requirement.strength,
                    requirement_id=requirement.requirement_id,
                )
            async with progress_lock:
                requirements_done += 1
                await self._progress(
                    phase="requirements",
                    clauses_total=clauses_total,
                    clauses_done=clauses_done,
                    requirements_total=len(requirements),
                    requirements_done=requirements_done,
                )
            return finding

        results = await asyncio.gather(
            *(
                analyze_requirement(index, requirement)
                for index, requirement in enumerate(requirements)
            ),
            return_exceptions=True,
        )
        findings: list[dict[str, Any]] = []
        for result in results:
            if isinstance(result, GapCheckCancelled):
                raise result
            if isinstance(result, Exception):
                raise result
            findings.append(cast(dict[str, Any], result))
        return findings

    async def _judge_clause(
        self,
        semaphore: asyncio.Semaphore,
        **kwargs: Any,
    ) -> tuple[ClauseJudgement | None, str]:
        async with semaphore:
            await self._check_cancel()
            try:
                judgement = await self.judge.judge_clause(**kwargs)
            except JudgeFailure as exc:
                self._judge_failures += 1
                self._usage = _add_usage(self._usage, exc.usage)
                if exc.reason == "token_cap":
                    self._caps_hit.add("tokens")
                return None, exc.reason
            self._usage = _add_usage(self._usage, judgement.usage)
            if judgement.cached:
                self._cache_hits += 1
            return judgement, ""

    async def _judge_requirement(
        self,
        semaphore: asyncio.Semaphore,
        **kwargs: Any,
    ) -> tuple[RequirementJudgement | None, str]:
        async with semaphore:
            await self._check_cancel()
            try:
                judgement = await self.judge.judge_requirement(**kwargs)
            except JudgeFailure as exc:
                self._judge_failures += 1
                self._usage = _add_usage(self._usage, exc.usage)
                if exc.reason == "token_cap":
                    self._caps_hit.add("tokens")
                return None, exc.reason
            self._usage = _add_usage(self._usage, judgement.usage)
            if judgement.cached:
                self._cache_hits += 1
            return judgement, ""

    async def _check_cancel(self) -> None:
        if self.cancel_check is not None and await self.cancel_check():
            raise GapCheckCancelled

    async def _progress(self, **update: Any) -> None:
        if self.progress_callback is not None:
            await self.progress_callback(update)


def _failure_rationale(reason: str) -> str:
    if reason == "token_cap":
        return "The per-run token cap was reached before this judgement."
    return (
        "The automated judgement was discarded after validation failed "
        f"({reason or 'unknown_reason'}). Manual review is required."
    )


def _add_usage(left: TokenUsage, right: TokenUsage) -> TokenUsage:
    return TokenUsage(
        input_tokens=left.input_tokens + right.input_tokens,
        output_tokens=left.output_tokens + right.output_tokens,
    )
