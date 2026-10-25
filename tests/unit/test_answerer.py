import json
from uuid import uuid4

import pytest

from app.llm.fake import FakeLLM, FakeResponse
from app.rag.answerer import Answerer
from app.rag.retriever import RetrievalResult
from app.store.base import SearchFilters, SearchHit


def _hit(score: float) -> SearchHit:
    return SearchHit(
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        text="Training records are retained.",
        score=score,
        page=2,
        section_heading=None,
        filename="doc.pdf",
        title="Document",
        source_agency="FDA",
        doc_type="guidance",
        year=2024,
        version="v1",
    )


class StubRetriever:
    def __init__(self, hit: SearchHit) -> None:
        self.hit = hit

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int,
        filters: SearchFilters | None = None,
        backend: str | None = None,
    ) -> RetrievalResult:
        return RetrievalResult(hits=(self.hit,), backend="pgvector", latency_ms=1.0)


@pytest.mark.asyncio
async def test_answerer_abstains_below_threshold_without_calling_llm() -> None:
    hit = _hit(0.749)
    llm = FakeLLM()
    answerer = Answerer(
        StubRetriever(hit),  # type: ignore[arg-type]
        llm,
        abstention_threshold=0.75,
        top_k=8,
    )

    result = await answerer.answer("question")

    assert result.insufficient_evidence is True
    assert result.grounding_reason == "below_threshold"
    assert result.citations == ()
    assert llm.requests == []


@pytest.mark.asyncio
async def test_answerer_calls_llm_at_threshold_and_validates_citation() -> None:
    hit = _hit(0.75)
    llm = FakeLLM(
        [
            FakeResponse(
                text=json.dumps({"answer": "Keep records.", "citations": [str(hit.chunk_id)]})
            )
        ]
    )
    answerer = Answerer(
        StubRetriever(hit),  # type: ignore[arg-type]
        llm,
        abstention_threshold=0.75,
        top_k=8,
    )

    result = await answerer.answer("question")

    assert result.insufficient_evidence is False
    assert result.grounded is True
    assert result.citations == (hit,)
    assert len(llm.requests) == 1
