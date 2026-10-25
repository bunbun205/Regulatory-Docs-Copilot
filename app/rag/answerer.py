from dataclasses import dataclass

from app.llm.base import LLMClient, TokenUsage
from app.rag.grounding import validate_answer
from app.rag.prompts import build_answer_messages
from app.rag.retriever import Backend, Retriever
from app.store.base import SearchFilters, SearchHit

INSUFFICIENT_ANSWER = "Insufficient evidence in the ingested corpus to answer this question."


@dataclass(frozen=True)
class AnswerResult:
    answer: str
    citations: tuple[SearchHit, ...]
    grounded: bool
    grounding_reason: str | None
    insufficient_evidence: bool
    backend: Backend
    top_score: float | None
    usage: TokenUsage
    retrieve_latency_ms: float
    generate_latency_ms: float


class Answerer:
    def __init__(
        self,
        retriever: Retriever,
        llm: LLMClient,
        *,
        abstention_threshold: float,
        top_k: int,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> None:
        self.retriever = retriever
        self.llm = llm
        self.abstention_threshold = abstention_threshold
        self.top_k = top_k
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def answer(
        self,
        query: str,
        *,
        filters: SearchFilters | None = None,
        backend: Backend | None = None,
    ) -> AnswerResult:
        retrieval = await self.retriever.retrieve(
            query,
            top_k=self.top_k,
            filters=filters,
            backend=backend,
        )
        top_score = retrieval.hits[0].score if retrieval.hits else None
        if top_score is None or top_score < self.abstention_threshold:
            return AnswerResult(
                answer=INSUFFICIENT_ANSWER,
                citations=(),
                grounded=False,
                grounding_reason="below_threshold",
                insufficient_evidence=True,
                backend=retrieval.backend,
                top_score=top_score,
                usage=TokenUsage(),
                retrieve_latency_ms=retrieval.latency_ms,
                generate_latency_ms=0.0,
            )

        result = await self.llm.chat(
            build_answer_messages(query, retrieval.hits),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        grounded = validate_answer(result.text, retrieval.hits)
        return AnswerResult(
            answer=grounded.answer,
            citations=grounded.citations,
            grounded=grounded.grounded,
            grounding_reason=grounded.reason,
            insufficient_evidence=False,
            backend=retrieval.backend,
            top_score=top_score,
            usage=result.usage,
            retrieve_latency_ms=retrieval.latency_ms,
            generate_latency_ms=round(result.latency_ms, 2),
        )
