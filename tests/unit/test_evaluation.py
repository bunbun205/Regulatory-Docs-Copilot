"""Evaluation failures and unreviewed labels must not become success metrics."""

import copy
import json
from dataclasses import asdict
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.llm.base import LLMResult
from app.rag.retriever import RetrievalResult
from app.store.base import SearchHit
from eval.datasets import (
    CleanReview,
    Defect,
    GapCase,
    Question,
    SourceLocation,
    load_jsonl,
    report_hash,
)
from eval.engine import corpus_snapshot, evaluate_gaps, evaluate_questions, validate_labels
from eval.fixture import FixtureEmbedder, run_fixture
from eval.metrics import (
    clean_false_positives,
    defect_detected,
    gap_citations,
    question_summary,
    retrieval_metrics,
    stability,
)
from eval.run import markdown, rescore_clean_reviews

REVIEW = {"verified": True, "reviewed_by": "Test oracle", "reviewed_at": "2026-10-26"}
SOURCE = {"filename": "one.txt", "content_sha256": "a" * 64, "page": 1, "quote": "Keep logs."}


def question(**kwargs):
    return Question.model_validate(
        {
            "id": "q",
            "kind": "answerable",
            "question": "What records?",
            "expected_sources": [SOURCE],
            **kwargs,
        }
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"verified": "false"},
        {"verified": True},
        {**REVIEW, "reviewed_by": " "},
        {**REVIEW, "kind": "unanswerable", "expected_sources": []},
        {"kind": "multi_document"},
        {"expected_sources": [SOURCE, SOURCE]},
        {"expected_sources": [{**SOURCE, "quote": " "}]},
        {"unexpected": "typo"},
    ],
)
def test_reject_misleading_review_labels(changes):
    with pytest.raises(ValidationError):
        question(**changes)


def test_duplicate_jsonl_ids_rejected(tmp_path):
    dataset = tmp_path / "questions.jsonl"
    dataset.write_text((question().model_dump_json() + "\n") * 2)
    with pytest.raises(ValueError, match="Duplicate IDs"):
        load_jsonl(dataset, Question)


def test_multi_document_recall_counts_each_target():
    first = SourceLocation(**SOURCE)
    second = SourceLocation(**{**SOURCE, "filename": "two.txt"})
    hit = {**SOURCE, "text": "Keep   logs.", "section_heading": None}
    score = retrieval_metrics([first, second], [{"text": "unrelated"}, hit, hit])
    assert score == {
        "targets": 2,
        "targets_found": 1,
        "recall_at_k": 0.5,
        "reciprocal_rank": 0.5,
        "all_sources_found": 0,
    }
    assert retrieval_metrics([first], [{**hit, "content_sha256": "b" * 64}])["targets_found"] == 0


def test_failed_verified_samples_remain_in_denominators():
    base = {"verified": True, "generation_enabled": True, "total_ms": 10}
    good = {
        **base,
        "kind": "answerable",
        "recall_at_k": 1,
        "reciprocal_rank": 1,
        "grounded": True,
        "proposed_citations": 2,
        "valid_citations": 1,
        "retrieve_ms": 3,
    }
    rows = [
        good,
        {**base, "kind": "answerable", "error": "TimeoutError"},
        {**base, "kind": "unanswerable", "abstained": True},
        {**base, "kind": "unanswerable", "error": "TimeoutError"},
        {**good, "verified": False},
    ]
    summary = question_summary(rows)
    assert summary["verified_questions"] == 4
    assert summary["failed_questions"] == 2
    for metric in (
        "retrieval_recall_at_k",
        "retrieval_mrr",
        "raw_citation_validity",
        "citation_valid_answer_rate",
        "abstention_accuracy",
    ):
        assert summary[metric] == 0.5
    assert summary["retrieval_latency"]["samples"] == 1
    assert question_summary([])["retrieval_recall_at_k"] is None
    assert question_summary([])["raw_citation_validity"] is None


def evidence():
    hit = SearchHit(
        UUID(int=1),
        UUID(int=2),
        0,
        "Keep logs. Sign checks.",
        0.9,
        1,
        None,
        "one.txt",
        "One",
        "Synthetic",
        "fixture",
        2026,
        "1",
    )
    chunks = {
        str(hit.chunk_id): {
            **asdict(hit),
            "document_id": str(hit.document_id),
            "content_sha256": SOURCE["content_sha256"],
        }
    }
    return hit, chunks


async def test_unverified_diagnostics_never_generate_or_score():
    hit, chunks = evidence()
    retriever = AsyncMock()
    retriever.retrieve.return_value = RetrievalResult((hit,), "pgvector", 12.0)
    llm = AsyncMock()
    config = Settings(_env_file=None)
    skipped = await evaluate_questions(
        [question()], retriever, chunks, "pgvector", config, llm, top_k=8
    )
    retriever.retrieve.assert_not_called()
    assert skipped["rows"] == []
    diagnostic = await evaluate_questions(
        [question()],
        retriever,
        chunks,
        "pgvector",
        config,
        llm,
        top_k=8,
        diagnostic_unverified=True,
    )
    llm.chat.assert_not_called()
    assert diagnostic["unverified_excluded"] == 1
    assert diagnostic["summary"]["verified_questions"] == 0
    assert diagnostic["summary"]["retrieval_recall_at_k"] is None
    assert diagnostic["summary"]["retrieval_latency"]["samples"] == 0
    assert diagnostic["diagnostics"]["retrieval_latency"]["samples"] == 1


async def test_proposed_invalid_citations_not_hidden_by_application_stripping():
    hit, chunks = evidence()
    retriever = AsyncMock()
    retriever.retrieve.return_value = RetrievalResult((hit,), "pgvector", 12.0)
    llm = AsyncMock()
    llm.chat.return_value = LLMResult(
        text=json.dumps({"answer": "Keep logs.", "citations": [str(hit.chunk_id), "invented", 123]})
    )
    result = await evaluate_questions(
        [question(**REVIEW)], retriever, chunks, "pgvector", Settings(_env_file=None), llm, top_k=8
    )
    assert result["summary"]["proposed_citations"] == 3
    assert result["summary"]["valid_citations"] == 1
    assert result["summary"]["raw_citation_validity"] == pytest.approx(1 / 3)
    assert result["summary"]["failed_questions"] == 0


async def test_stale_backend_chunk_is_failure_not_a_retrieval_hit():
    hit, chunks = evidence()
    chunks[str(hit.chunk_id)]["text"] = "changed"
    retriever = AsyncMock()
    retriever.retrieve.return_value = RetrievalResult((hit,), "qdrant", 12.0)
    result = await evaluate_questions(
        [question(**REVIEW)], retriever, chunks, "qdrant", Settings(_env_file=None), None, top_k=8
    )
    assert result["summary"]["retrieval_recall_at_k"] == 0
    assert result["summary"]["failed_questions"] == 1


def test_reviewed_source_and_snapshot_must_match_corpus():
    _, chunks = evidence()
    validate_labels([question(**REVIEW)], [], chunks)
    with pytest.raises(ValueError, match="snapshot"):
        validate_labels([question(**REVIEW, corpus_snapshot="b" * 64)], [], chunks)
    with pytest.raises(ValueError, match="absent"):
        validate_labels([question(**REVIEW, expected_sources=[{**SOURCE, "page": 2}])], [], chunks)


def report_evidence():
    hit, chunks = evidence()
    report = {
        "sop_clauses": [{"clause_id": "SOP-001", "text": "Discard logs."}],
        "findings": [
            {
                "finding_id": "GAP-0001",
                "direction": "sop_to_regulation",
                "verdict": "conflict",
                "sop_clause_refs": ["SOP-001"],
                "regulation_citations": [
                    {
                        "chunk_id": str(hit.chunk_id),
                        "document_id": str(hit.document_id),
                        "page": 1,
                        "snippet": "Keep logs.",
                    }
                ],
            }
        ],
    }
    return report, chunks


def test_defect_requires_correct_source_clause_and_requirement():
    report, chunks = report_evidence()
    defect = Defect(
        id="d",
        direction="sop_to_regulation",
        verdicts=["conflict"],
        source=SOURCE,
        sop_quote="Discard logs.",
        description="Contradiction",
    )
    assert defect_detected(defect, report, chunks)
    assert not defect_detected(defect.model_copy(update={"sop_quote": "different"}), report, chunks)
    report["findings"][0].update(direction="regulation_to_sop", verdict="missing")
    omission = Defect(
        id="o",
        direction="regulation_to_sop",
        verdicts=["missing"],
        source=SOURCE,
        requirement_quote="Sign checks.",
        description="Omission",
    )
    assert not defect_detected(omission, report, chunks)  # Same chunk, different obligation.
    report["findings"][0]["regulation_citations"][0]["snippet"] = "Sign checks."
    assert defect_detected(omission, report, chunks)
    report["findings"][0]["regulation_citations"][0]["document_id"] = "wrong"
    assert not defect_detected(omission, report, chunks)


def test_citation_validity_checks_locations_snippets_and_sop_refs():
    report, chunks = report_evidence()
    assert gap_citations(report, chunks) == (2, 2)
    report["findings"][0]["regulation_citations"][0]["snippet"] = "invented quote"
    report["findings"][0]["sop_clause_refs"] = ["SOP-999"]
    assert gap_citations(report, chunks) == (0, 2)


def review_for(report, ids):
    return CleanReview(
        report_sha256=report_hash(report),
        reviewed_by="Test oracle",
        reviewed_at="2026-10-26",
        false_positive_ids=ids,
    )


def test_clean_false_positives_require_exact_report_review():
    report, _ = report_evidence()
    assert clean_false_positives(report, []) is None
    review = review_for(report, ["GAP-0001"])
    assert clean_false_positives(report, [review]) == (1, 1)
    with pytest.raises(ValueError):
        clean_false_positives(report, [review_for(report, ["GAP-0001", "GAP-0001"])])
    with pytest.raises(ValueError):
        clean_false_positives(report, [review_for(report, ["unknown"])])
    report["findings"][0]["verdict"] = "judge_failed"
    assert clean_false_positives(report, [review]) is None
    assert clean_false_positives(report, [review_for(report, [])]) == (0, 0)


def test_rescore_uses_exact_saved_report_without_model_calls(tmp_path):
    report, _ = report_evidence()
    digest = report_hash(report)
    saved = tmp_path / f"{digest}.json"
    saved.write_text(json.dumps(report))
    result = {
        "backends": {
            "pgvector": {"gaps": {"rows": [{"kind": "clean", "runs": [{"report_sha256": digest}]}]}}
        }
    }
    scored = rescore_clean_reviews(result, [review_for(report, ["GAP-0001"])], tmp_path)
    assert scored["backends"]["pgvector"]["gaps"]["clean_false_positive_rate"] == 1
    report["other"] = "tampered"
    saved.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="changed"):
        rescore_clean_reviews(
            result,
            [
                CleanReview(
                    report_sha256=digest,
                    reviewed_by="Test",
                    reviewed_at="2026-10-26",
                    false_positive_ids=[],
                )
            ],
            tmp_path,
        )


def test_stability_detects_verdict_changes_and_missing_findings_not_generated_ids():
    report, _ = report_evidence()
    same = copy.deepcopy(report)
    same["findings"][0].update(finding_id="other", requirement_id="REQ-099")
    assert stability([report, same])["verdict_set_jaccard"] == 1
    same["findings"][0]["verdict"] = "partial"
    assert stability([report, same])["verdict_set_jaccard"] == 0
    assert stability([report, {"findings": []}])["verdict_set_jaccard"] == 0
    assert stability([{"findings": []}, {"findings": []}])["verdict_set_jaccard"] is None


async def test_failed_mutations_count_and_unverified_sops_are_not_opened(tmp_path):
    from eval.datasets import file_hash

    report, chunks = report_evidence()
    sop = tmp_path / "mutation.txt"
    sop.write_text("Discard logs.")
    common = {
        "sop_path": sop.name,
        "sop_sha256": file_hash(sop),
        "provenance": "Test fixture",
        "corpus_snapshot": corpus_snapshot(chunks),
    }
    clean = GapCase(id="clean", kind="clean", **REVIEW, **common)
    mutation = GapCase(
        id="mutation",
        kind="mutation",
        baseline_id="clean",
        **REVIEW,
        **common,
        defects=[
            {
                "id": "d",
                "direction": "sop_to_regulation",
                "verdicts": ["conflict"],
                "source": SOURCE,
                "sop_quote": "Discard logs.",
                "description": "Contradiction",
            }
        ],
    )
    candidate = GapCase(
        id="unreviewed",
        kind="clean",
        sop_path="missing-file.txt",
        sop_sha256="a" * 64,
        provenance="Not supplied yet",
    )
    with pytest.raises(ValueError, match="baseline"):
        validate_labels([], [mutation], chunks)
    validate_labels([], [clean, mutation], chunks)
    result = await evaluate_gaps(
        [mutation, candidate],
        tmp_path,
        AsyncMock(),
        FixtureEmbedder(),
        None,
        chunks,
        "pgvector",
        Settings(_env_file=None),
        2,
        [],
        tmp_path,
    )
    assert result["unverified_excluded"] == 1
    assert result["failed_runs"] == 2
    assert result["defects_expected_across_repeats"] == 2
    assert result["injected_defect_recall"] == 0
    assert result["clean_false_positive_rate"] is None
    sop.write_text("Changed after review.")
    with pytest.raises(ValueError, match="SOP changed"):
        await evaluate_gaps(
            [mutation],
            tmp_path,
            AsyncMock(),
            FixtureEmbedder(),
            None,
            chunks,
            "pgvector",
            Settings(_env_file=None),
            2,
            [],
            tmp_path,
        )


async def test_synthetic_regression_is_explicit_and_exercises_real_pipelines():
    result = await run_fixture()
    assert result["dataset_kind"] == "synthetic_ci_fixture_only"
    assert result["verification_status"] == "synthetic_regression_pass"
    rendered = markdown(result)
    assert "not pgvector/Qdrant" in rendered
    assert "unavailable" in rendered  # Human-reviewed clean false positives unavailable.
