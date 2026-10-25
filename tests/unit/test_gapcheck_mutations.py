import json
from pathlib import Path
from uuid import uuid4

from app.gapcheck.judge import ClauseJudgement, RequirementJudgement
from app.gapcheck.requirements import Requirement, extract_requirements
from app.gapcheck.runner import GapCheckConfig, GapCheckRunner
from app.llm.base import TokenUsage
from app.rag.retriever import RetrievalResult
from app.store.base import SearchFilters, SearchHit
from tests.helpers import FakeEmbedder

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "gapcheck"
GROUND_TRUTH = json.loads((FIXTURE_DIR / "ground_truth.json").read_text(encoding="utf-8"))
REGULATION_TEXT = GROUND_TRUTH["regulation_text"]


class FixtureRetriever:
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
        return RetrievalResult(hits=(self.hit,), backend="pgvector", latency_ms=0.0)


class DeterministicFixtureJudge:
    """Text-driven judge for CI regression only; it is not an LLM quality metric."""

    async def judge_clause(
        self,
        *,
        clause_id: str,
        clause_text: str,
        section: str,
        retrieved_hits: list[SearchHit],
    ) -> ClauseJudgement:
        lowered = clause_text.lower()
        conflict = any(
            marker in lowered
            for marker in (
                "not limited to authorized personnel",
                "deleted at any time",
                "deleted after one year",
            )
        )
        return ClauseJudgement(
            verdict="conflict" if conflict else "compliant",
            citations=(str(retrieved_hits[0].chunk_id),),
            rationale="Deterministic fixture judgement.",
            usage=TokenUsage(),
        )

    async def judge_requirement(
        self,
        *,
        requirement: Requirement,
        candidate_clauses: list[dict[str, str]],
    ) -> RequirementJudgement:
        texts = [clause["text"].lower() for clause in candidate_clauses]
        if "authenticity" in requirement.text.lower():
            matched = next(
                (
                    clause
                    for clause in candidate_clauses
                    if "closed electronic record system" in clause["text"].lower()
                ),
                None,
            )
        elif "authority checks" in requirement.text.lower():
            matched = next(
                (
                    clause
                    for clause in candidate_clauses
                    if "access to the system is limited to authorized personnel"
                    in clause["text"].lower()
                ),
                None,
            )
        elif "training" in requirement.text.lower():
            matched = next(
                (
                    clause
                    for clause in candidate_clauses
                    if "complete training" in clause["text"].lower()
                ),
                None,
            )
        else:
            matched = None
        if matched is None:
            return RequirementJudgement(
                verdict="missing",
                citations=(),
                rationale=f"No SOP clause matched: {', '.join(texts)[:100]}",
                usage=TokenUsage(),
            )
        return RequirementJudgement(
            verdict="addressed",
            citations=(matched["clause_id"],),
            rationale="The SOP clause addresses the requirement.",
            usage=TokenUsage(),
        )


def _hit() -> SearchHit:
    return SearchHit(
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        text=REGULATION_TEXT,
        score=0.9,
        page=2,
        section_heading="Electronic records",
        filename="part11.pdf",
        title="21 CFR Part 11",
        source_agency="FDA",
        doc_type="regulation",
        year=2026,
        version="v1",
    )


async def _run_fixture(name: str) -> tuple[dict, dict[str, str]]:
    hit = _hit()
    text = (FIXTURE_DIR / f"{name}.md").read_text(encoding="utf-8")
    runner = GapCheckRunner(
        FixtureRetriever(hit),  # type: ignore[arg-type]
        FakeEmbedder(),
        DeterministicFixtureJudge(),  # type: ignore[arg-type]
        GapCheckConfig(
            max_clauses=20,
            max_requirements=20,
            relevance_threshold=0.5,
            sop_match_top_k=10,
            judge_concurrency=2,
            retrieval_concurrency=2,
        ),
        job_id=str(uuid4()),
        model_label="fixture:deterministic",
    )
    report = await runner.run(text)
    clauses = {clause["clause_id"]: clause["text"] for clause in report["sop_clauses"]}
    _assert_citations_valid(report, hit, clauses)
    return report, clauses


def _assert_citations_valid(
    report: dict,
    hit: SearchHit,
    clauses: dict[str, str],
) -> None:
    for finding in report["findings"]:
        assert set(finding["sop_clause_refs"]) <= set(clauses)
        for citation in finding["regulation_citations"]:
            assert citation["chunk_id"] == str(hit.chunk_id)


def _find_defect(
    report: dict,
    *,
    direction: str,
    verdict: str,
    clause_text_contains: str | None = None,
    clauses: dict[str, str],
    requirement_text_contains: str | None = None,
) -> dict:
    requirements, _ = extract_requirements(
        [
            SearchHit(
                chunk_id=uuid4(),
                document_id=uuid4(),
                chunk_index=0,
                text=REGULATION_TEXT,
                score=0.9,
                page=2,
                section_heading=None,
                filename="part11.pdf",
                title="21 CFR Part 11",
                source_agency="FDA",
                doc_type="regulation",
                year=2026,
                version="v1",
            )
        ],
        max_requirements=20,
    )
    requirement_id = None
    if requirement_text_contains is not None:
        requirement_id = next(
            requirement.requirement_id
            for requirement in requirements
            if requirement_text_contains in requirement.text.lower()
        )
    for finding in report["findings"]:
        if finding["direction"] != direction or finding["verdict"] != verdict:
            continue
        if clause_text_contains is not None and not any(
            clause_text_contains.lower() in clauses[ref].lower()
            for ref in finding["sop_clause_refs"]
        ):
            continue
        if requirement_id is not None and finding["requirement_id"] != requirement_id:
            continue
        return finding
    raise AssertionError(
        f"Expected defect not found: direction={direction}, verdict={verdict}, "
        f"clause={clause_text_contains}, requirement={requirement_text_contains}"
    )


async def test_clean_fixture_has_no_unsupported_claims() -> None:
    report, _ = await _run_fixture("clean_sop")

    assert report["findings"]
    assert not {
        finding["verdict"]
        for finding in report["findings"]
        if finding["verdict"] in {"conflict", "missing", "judge_failed", "not_covered_by_corpus"}
    }
    assert report["counts_by_severity"]["high"] == 0


async def test_mutation_fixtures_detect_injected_defects_with_citations() -> None:
    for name, expected in GROUND_TRUTH["fixtures"].items():
        if name == "clean_sop":
            continue
        report, clauses = await _run_fixture(name)
        for defect in expected["expected_defects"]:
            finding = _find_defect(
                report,
                direction=defect["direction"],
                verdict=defect["verdict"],
                clause_text_contains=defect.get("clause_text_contains"),
                requirement_text_contains=defect.get("requirement_text_contains"),
                clauses=clauses,
            )
            assert finding["regulation_citations"], name
            assert finding["rationale"], name


async def test_injection_fixture_does_not_become_a_compliant_finding() -> None:
    report, clauses = await _run_fixture("injection")
    injection_clause_id = next(
        clause_id
        for clause_id, text in clauses.items()
        if "Ignore all previous instructions" in text
    )

    injection_findings = [
        finding
        for finding in report["findings"]
        if injection_clause_id in finding["sop_clause_refs"]
    ]
    assert injection_findings
    assert all(finding["verdict"] != "compliant" for finding in injection_findings)
    assert any(finding["verdict"] == "conflict" for finding in injection_findings)
