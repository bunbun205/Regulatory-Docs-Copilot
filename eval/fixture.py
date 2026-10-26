"""Synthetic CI regression only; no human or regulatory ground truth is claimed."""

import json
import re
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

import numpy as np

from app.core.config import Settings
from app.llm.base import LLMResult, TokenUsage
from app.rag.retriever import Retriever
from app.store.base import SearchHit
from eval.datasets import GapCase, Question, file_hash
from eval.engine import corpus_snapshot, evaluate_gaps, evaluate_questions


class FixtureEmbedder:
    dimension = 384

    def embed(self, texts):
        vectors = np.zeros((len(texts), self.dimension), dtype=np.float32)
        for i, text in enumerate(texts):
            vectors[i, 0] = "alpha" in text.lower()
            vectors[i, 1] = "beta" in text.lower()
            if not vectors[i].any():
                vectors[i, 2] = 1
            vectors[i] /= np.linalg.norm(vectors[i])
        return vectors


class FixtureStore:
    name = "synthetic_numpy"

    def __init__(self, hits):
        self.hits = hits
        self.vectors = FixtureEmbedder().embed([h.text for h in hits])

    async def search(self, vector, top_k, filters=None):
        scores = self.vectors @ np.asarray(vector)
        return [
            replace(self.hits[int(i)], score=float(scores[i])) for i in np.argsort(-scores)[:top_k]
        ]


class FixtureLLM:
    async def chat(self, messages, **kwargs):
        user = messages[-1].content
        if "<regulation_requirement" in user:
            missing = "destroyed" in user
            payload = {
                "verdict": "missing" if missing else "addressed",
                "citations": [] if missing else ["SOP-001"],
                "rationale": "Synthetic fixture rule.",
            }
        elif "<sop_clause " in user:
            payload = {
                "verdict": "conflict" if "destroyed" in user else "compliant",
                "citations": re.findall(r"chunk_id=([0-9a-f-]+)", user),
                "rationale": "Synthetic fixture rule.",
            }
        else:
            payload = {
                "answer": "Synthetic fixture answer.",
                "citations": re.findall(r"chunk_id=([0-9a-f-]+)", user),
            }
        return LLMResult(text=json.dumps(payload), usage=TokenUsage(40, 10))

    async def close(self):
        pass


async def run_fixture() -> dict:
    hits = [
        SearchHit(
            chunk_id=UUID(int=i),
            document_id=UUID(int=i + 10),
            chunk_index=0,
            text=text,
            score=1.0,
            page=1,
            section_heading=None,
            filename=f"fixture-{i}.txt",
            title=f"Synthetic fixture {i}",
            source_agency="Synthetic",
            doc_type="fixture",
            year=2026,
            version="1",
        )
        for i, text in enumerate(
            ["Alpha staff shall record checks.", "Beta staff shall sign logs."], 1
        )
    ]
    chunks = {
        str(h.chunk_id): {
            **asdict(h),
            "chunk_id": str(h.chunk_id),
            "document_id": str(h.document_id),
            "content_sha256": str(i) * 64,
        }
        for i, h in enumerate(hits, 1)
    }
    snapshot = corpus_snapshot(chunks)
    sources = [
        {
            "filename": h.filename,
            "content_sha256": chunks[str(h.chunk_id)]["content_sha256"],
            "page": 1,
            "quote": h.text,
        }
        for h in hits
    ]
    # Eligibility here is explicitly a code-defined fixture oracle. These rows
    # are never loaded by the real corpus command or merged into author datasets.
    fixture_review = {
        "verified": True,
        "reviewed_by": "synthetic-code-fixture (not a human review)",
        "reviewed_at": "2026-10-26",
        "notes": "Regression oracle only.",
    }
    questions = [
        Question(
            id="fixture-one",
            question="Alpha controls?",
            kind="answerable",
            expected_sources=sources[:1],
            **fixture_review,
        ),
        Question(
            id="fixture-multi",
            question="Alpha and beta controls?",
            kind="multi_document",
            expected_sources=sources,
            **fixture_review,
        ),
        Question(
            id="fixture-unknown",
            question="Gamma controls?",
            kind="unanswerable",
            corpus_snapshot=snapshot,
            **fixture_review,
        ),
    ]
    embedder = FixtureEmbedder()
    retriever = Retriever(embedder, {"pgvector": FixtureStore(hits)}, "pgvector")
    llm = FixtureLLM()
    config = Settings(
        _env_file=None,
        LLM_PROVIDER="fake",
        LLM_MODEL="synthetic-fixture",
        ABSTENTION_THRESHOLD=0.5,
        GAPCHECK_RELEVANCE_THRESHOLD=0.5,
    )
    q = await evaluate_questions(questions, retriever, chunks, "pgvector", config, llm, top_k=2)
    with TemporaryDirectory(prefix="labdocs-eval-fixture-") as temporary:
        directory = Path(temporary)
        (directory / "clean.txt").write_text("Alpha checks are recorded.")
        (directory / "mutation.txt").write_text("Alpha checks are destroyed.")
        common = {
            **fixture_review,
            "corpus_snapshot": snapshot,
            "provenance": "Synthetic CI fixture, not a human-authored SOP.",
        }
        cases = [
            GapCase(
                id="fixture-clean",
                kind="clean",
                sop_path="clean.txt",
                sop_sha256=file_hash(directory / "clean.txt"),
                **common,
            ),
            GapCase(
                id="fixture-mutation",
                kind="mutation",
                baseline_id="fixture-clean",
                sop_path="mutation.txt",
                sop_sha256=file_hash(directory / "mutation.txt"),
                defects=[
                    {
                        "id": "destroyed",
                        "direction": "sop_to_regulation",
                        "verdicts": ["conflict"],
                        "source": sources[0],
                        "sop_quote": "Alpha checks are destroyed.",
                        "description": "Synthetic contrary action.",
                    }
                ],
                **common,
            ),
        ]
        g = await evaluate_gaps(
            cases,
            directory,
            retriever,
            embedder,
            llm,
            chunks,
            "pgvector",
            config,
            2,
            [],
            directory / "review",
        )
    assert q["summary"]["retrieval_recall_at_k"] == 1
    assert q["summary"]["retrieval_mrr"] == 1
    assert q["summary"]["raw_citation_validity"] == 1
    assert q["summary"]["abstention_accuracy"] == 1
    assert q["summary"]["failed_questions"] == 0
    assert g["injected_defect_recall"] == 1 and g["citation_validity"] == 1
    assert g["failed_runs"] == 0 and g["clean_false_positive_rate"] is None
    assert all(c["stability"]["verdict_set_jaccard"] == 1 for c in g["rows"])
    return {
        "schema_version": 1,
        "dataset_kind": "synthetic_ci_fixture_only",
        "verification_status": "synthetic_regression_pass",
        "created_at": datetime.now(UTC).isoformat(),
        "corpus_snapshot": snapshot,
        "provider": "fake",
        "model": "synthetic-fixture",
        "top_k": 2,
        "backends": {"synthetic_numpy (not pgvector/Qdrant)": {"questions": q, "gaps": g}},
        "limitations": [
            "All fixtures and expected outcomes are synthetic code-defined regression oracles, "
            "not human-verified quality evidence.",
            "This does not measure either real vector backend or any production model.",
            "No clean false-positive rate is invented without an exact-report human review.",
        ],
    }
