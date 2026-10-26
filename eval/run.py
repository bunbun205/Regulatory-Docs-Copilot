"""Run corpus evaluation or the explicit synthetic CI regression fixture."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.db.models import Chunk, Document
from app.db.session import Database
from app.ingest.embedding import SentenceTransformerEmbedder
from app.llm.factory import build_llm_client
from app.rag.retriever import Retriever
from app.store.pgvector_store import PgVectorStore
from app.store.qdrant_store import QdrantStore
from eval.datasets import CleanReview, GapCase, Question, file_hash, load_jsonl, report_hash
from eval.engine import corpus_snapshot, evaluate_gaps, evaluate_questions, validate_labels
from eval.metrics import clean_false_positives, ratio


async def load_corpus(database: Database) -> dict[str, dict]:
    async with database.sessionmaker() as session:
        rows = (
            await session.execute(
                select(Chunk, Document).join(Document, Chunk.document_id == Document.id)
            )
        ).all()
    return {
        str(chunk.id): {
            "chunk_id": str(chunk.id),
            "document_id": str(document.id),
            "filename": document.filename,
            "content_sha256": document.content_sha256,
            "page": chunk.page,
            "section_heading": chunk.section_heading,
            "text": chunk.text,
        }
        for chunk, document in rows
    }


def load_reviews(path: Path) -> list[CleanReview]:
    reviews = [CleanReview.model_validate(r) for r in json.loads(path.read_text())]
    if len({r.report_sha256 for r in reviews}) != len(reviews):
        raise ValueError("Duplicate clean report reviews.")
    return reviews


async def run_corpus(args: argparse.Namespace) -> dict[str, Any]:
    questions = load_jsonl(args.questions, Question)
    cases = load_jsonl(args.mutations, GapCase)
    reviews = load_reviews(args.clean_reviews)
    database = Database(settings.DATABASE_URL)
    qdrant = None
    llm = None
    try:
        chunks = await load_corpus(database)
        if not chunks:
            raise ValueError("The corpus is empty. Ingest the author's documents first.")
        validate_labels(questions, cases, chunks)
        backends = ["pgvector", "qdrant"] if args.backend == "both" else [args.backend]
        stores = {"pgvector": PgVectorStore(database.sessionmaker)}
        if "qdrant" in backends:
            qdrant = QdrantStore(
                settings.QDRANT_URL,
                settings.QDRANT_COLLECTION,
                dimension=settings.EMBEDDING_DIMENSION,
                api_key=settings.QDRANT_API_KEY,
                timeout=settings.QDRANT_TIMEOUT_SECONDS,
            )
            # Evaluation requires an existing corpus; never intentionally create one.
            await qdrant._client.get_collection(qdrant.collection)
            stores["qdrant"] = qdrant
        embedder = SentenceTransformerEmbedder(
            settings.EMBEDDING_MODEL,
            dimension=settings.EMBEDDING_DIMENSION,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
        )
        retriever = Retriever(embedder, stores, "pgvector")
        if not args.retrieval_only and (
            any(q.verified for q in questions) or any(c.verified for c in cases)
        ):
            llm = build_llm_client(settings)
        if (
            any(q.verified for q in questions)
            or args.diagnostic_unverified
            or any(c.verified for c in cases)
        ):
            await asyncio.to_thread(embedder.embed, ["Evaluation warmup."])
        result: dict[str, Any] = {
            "schema_version": 1,
            "dataset_kind": "author_corpus",
            "created_at": datetime.now(UTC).isoformat(),
            "corpus_snapshot": corpus_snapshot(chunks),
            "documents": len({c["document_id"] for c in chunks.values()}),
            "postgres_chunks": len(chunks),
            "dataset_hashes": {
                "questions": file_hash(args.questions),
                "mutations": file_hash(args.mutations),
            },
            "provider": settings.LLM_PROVIDER,
            "model": settings.LLM_MODEL,
            "embedding_model": settings.EMBEDDING_MODEL,
            "top_k": args.top_k,
            "abstention_threshold": settings.ABSTENTION_THRESHOLD,
            "retrieval_only": args.retrieval_only,
            "gap_repeats": args.repeats,
            "timing_method": (
                "Sequential queries per backend, embedding warmed once, "
                "no generation cache; backend order as listed."
            ),
            "verification_status": "awaiting_human_review"
            if not questions
            or not cases
            or any(not q.verified for q in questions)
            or any(not c.verified for c in cases)
            else "reviewed_inputs",
            "backends": {},
        }
        for backend in backends:
            count = await stores[backend].count()
            if count != len(chunks):
                raise ValueError(
                    f"{backend}: chunk count differs from the Postgres corpus snapshot."
                )
            result["backends"][backend] = {
                "store_chunks": count,
                "questions": await evaluate_questions(
                    questions,
                    retriever,
                    chunks,
                    backend,
                    settings,
                    llm,
                    top_k=args.top_k,
                    diagnostic_unverified=args.diagnostic_unverified,
                ),
                "gaps": await evaluate_gaps(
                    cases if not args.retrieval_only else [],
                    args.mutations.parent,
                    retriever,
                    embedder,
                    llm,
                    chunks,
                    backend,
                    settings,
                    args.repeats,
                    reviews,
                    args.review_dir,
                ),
            }
            result["backends"][backend]["gaps"]["skipped_retrieval_only"] = args.retrieval_only
        if len(backends) == 2:
            paired = []
            other = {r["id"]: r for r in result["backends"]["qdrant"]["questions"]["rows"]}
            for row in result["backends"]["pgvector"]["questions"]["rows"]:
                counterpart = other[row["id"]]
                if row.get("error") or counterpart.get("error"):
                    continue
                a, b = row["retrieved_chunk_ids"], counterpart["retrieved_chunk_ids"]
                union = set(a) | set(b)
                paired.append(
                    {
                        "id": row["id"],
                        "same_order": a == b,
                        "hit_set_jaccard": len(set(a) & set(b)) / len(union) if union else None,
                    }
                )
            result["backend_agreement_diagnostic"] = paired
        result["limitations"] = [
            "Unverified labels are excluded from all quality denominators, including diagnostics.",
            "Citation validity checks IDs/locations, not semantic support or legal correctness.",
            "Failed verified queries and mutation runs remain in recall/abstention denominators.",
            "Clean false-positive rates require a human review bound to each exact report hash.",
            "Stability includes failure verdicts and is not an accuracy measure; "
            "raw gap evidence stays local in the review directory.",
        ]
        return result
    finally:
        if llm is not None:
            await llm.close()
        if qdrant is not None:
            await qdrant.close()
        await database.dispose()


def rescore_clean_reviews(result: dict, reviews: list[CleanReview], review_dir: Path) -> dict:
    for backend in result["backends"].values():
        gaps = backend["gaps"]
        positives = denominator = reviewed_count = 0
        for case in gaps["rows"]:
            if case["kind"] != "clean":
                continue
            for run in case["runs"]:
                digest = run.get("report_sha256")
                if not digest or not any(r.report_sha256 == digest for r in reviews):
                    continue
                report = json.loads((review_dir / f"{digest}.json").read_text())
                if report_hash(report) != digest:
                    raise ValueError("Local report changed after review.")
                reviewed = clean_false_positives(report, reviews)
                if reviewed is not None:
                    positives += reviewed[0]
                    denominator += reviewed[1]
                    reviewed_count += 1
        gaps.update(
            clean_false_positives=positives,
            clean_reviewed_determinate_findings=denominator,
            clean_reviewed_runs=reviewed_count,
            clean_false_positive_rate=ratio(positives, denominator),
        )
    result["rescored_at"] = datetime.now(UTC).isoformat()
    return result


def markdown(result: dict) -> str:
    def value(v: Any) -> str:
        return "unavailable" if v is None else f"{v:.4f}" if isinstance(v, float) else str(v)

    def row(values: list) -> str:
        return (
            "| "
            + " | ".join(value(v).replace("|", "\\|").replace("\n", " ") for v in values)
            + " |"
        )

    lines = [
        "# Evaluation report",
        "",
        f"Dataset: **{result['dataset_kind']}**. Status: **{result['verification_status']}**.",
        "",
        f"Provider/model: `{result['provider']}:{result['model']}`.",
        "Generation disabled: no model calls were made."
        if result.get("retrieval_only")
        else "Generation uses the configured provider for eligible samples only.",
        f"Corpus snapshot: `{result['corpus_snapshot']}`.",
        "",
        row(
            [
                "Backend",
                "Verified queries",
                "Recall@k",
                "MRR",
                "Raw citation validity",
                "Abstention accuracy",
                "Failed queries",
                "Retrieve p50/p95 ms",
            ]
        ),
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name, data in result["backends"].items():
        q = data["questions"]["summary"]
        latency = q["retrieval_latency"]
        lines.append(
            row(
                [
                    name,
                    q["verified_questions"],
                    q["retrieval_recall_at_k"],
                    q["retrieval_mrr"],
                    q["raw_citation_validity"],
                    q["abstention_accuracy"],
                    q["failed_questions"],
                    f"{value(latency['p50_ms'])} / {value(latency['p95_ms'])}",
                ]
            )
        )
    if any(
        d["questions"].get("diagnostic_unverified_queries") for d in result["backends"].values()
    ):
        lines += [
            "",
            "Unreviewed retrieval diagnostics (excluded from quality scores):",
            "",
            row(["Backend", "Queries", "Failed", "Retrieve p50/p95 ms"]),
            "|---|---:|---:|---|",
        ]
        for name, data in result["backends"].items():
            q = data["questions"]
            latency = q["diagnostics"]["retrieval_latency"]
            lines.append(
                row(
                    [
                        name,
                        q["diagnostic_unverified_queries"],
                        q["diagnostics"]["failed_queries"],
                        f"{value(latency['p50_ms'])} / {value(latency['p95_ms'])}",
                    ]
                )
            )
    lines += [
        "",
        row(
            [
                "Backend",
                "Verified gap cases",
                "Defects detected/expected",
                "Defect recall",
                "Citation validity",
                "Reviewed clean findings",
                "Clean false-positive rate",
                "Failed runs",
            ]
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, data in result["backends"].items():
        g = data["gaps"]
        lines.append(
            row(
                [
                    name,
                    g["verified_cases"],
                    f"{g['defects_detected']}/{g['defects_expected_across_repeats']}",
                    g["injected_defect_recall"],
                    g["citation_validity"],
                    g["clean_reviewed_determinate_findings"],
                    g["clean_false_positive_rate"],
                    g["failed_runs"],
                ]
            )
        )
        for case in g["rows"]:
            score = value(case["stability"]["verdict_set_jaccard"])
            pairs = case["stability"]["comparisons"]
            lines.append(
                f"\n{name}, case `{case['id']}`: verdict-set Jaccard {score} "
                f"across {pairs} successful nonempty report pairs."
            )
    lines += ["", "## Method and limits", "", result.get("timing_method", ""), ""]
    lines += [f"- {text}" for text in result.get("limitations", [])]
    lines += [
        "",
        "Unreviewed datasets are not a completed quality evaluation. Consult the companion "
        "JSON for sample counts, exclusions, failures and individual results. "
        "This report does not establish regulatory compliance.",
        "",
    ]
    return "\n".join(lines)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["pgvector", "qdrant", "both"], default="both")
    parser.add_argument("--questions", type=Path, default=Path("eval/golden.jsonl"))
    parser.add_argument("--mutations", type=Path, default=Path("eval/mutations.jsonl"))
    parser.add_argument("--clean-reviews", type=Path, default=Path("eval/clean_reviews.json"))
    parser.add_argument("--review-dir", type=Path, default=Path("eval/review"))
    parser.add_argument("--output-dir", type=Path, default=Path("eval/reports"))
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--diagnostic-unverified", action="store_true")
    parser.add_argument("--retrieval-only", action="store_true")
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--rescore-report", type=Path)
    args = parser.parse_args()
    if not 1 <= args.top_k <= 50 or not 2 <= args.repeats <= 10:
        parser.error("top-k must be 1–50 and repeats 2–10")
    if args.fixture:
        from eval.fixture import run_fixture

        result = await run_fixture()
    elif args.rescore_report:
        result = rescore_clean_reviews(
            json.loads(args.rescore_report.read_text()),
            load_reviews(args.clean_reviews),
            args.review_dir,
        )
    else:
        result = await run_corpus(args)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    json_path = args.output_dir / f"{stem}.json"
    json_path.write_text(json.dumps(result, indent=2) + "\n")
    (args.output_dir / f"{stem}.md").write_text(markdown(result))
    print(json_path)
    print(f"Verification status: {result['verification_status']}")
    failures = any(
        d["questions"]["summary"]["failed_questions"]
        or d["questions"]["diagnostics"]["failed_queries"]
        or d["gaps"]["failed_runs"]
        for d in result["backends"].values()
    )
    return 1 if failures else 2 if result["verification_status"] == "awaiting_human_review" else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
