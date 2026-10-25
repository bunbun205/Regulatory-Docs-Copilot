"""Measure retrieval top-1 scores for in-corpus and out-of-corpus questions.

This is deliberately a probe, not the full evaluation harness. It reuses the
real embedder and vector stores so the abstention threshold is selected from
observed scores rather than from intuition.
"""

import argparse
import asyncio
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Literal, cast

from app.core.config import settings
from app.db.session import Database
from app.ingest.embedding import SentenceTransformerEmbedder
from app.store.base import SearchFilters
from app.store.pgvector_store import PgVectorStore
from app.store.qdrant_store import QdrantStore

Backend = Literal["pgvector", "qdrant"]


def _load_questions(path: Path) -> list[dict[str, str]]:
    questions = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("group") not in {"in_corpus", "out_of_corpus"}:
            raise ValueError(f"Line {line_number}: invalid group.")
        questions.append(row)
    return questions


def _summary(scores: list[float]) -> dict[str, float | int]:
    return {
        "count": len(scores),
        "min": round(min(scores), 6),
        "p50": round(statistics.median(scores), 6),
        "max": round(max(scores), 6),
        "mean": round(statistics.mean(scores), 6),
    }


async def _run(questions: list[dict[str, str]], backend: Backend, top_k: int) -> dict[str, Any]:
    database = Database(settings.DATABASE_URL)
    qdrant = QdrantStore(
        settings.QDRANT_URL,
        settings.QDRANT_COLLECTION,
        dimension=settings.EMBEDDING_DIMENSION,
        api_key=settings.QDRANT_API_KEY,
        timeout=settings.QDRANT_TIMEOUT_SECONDS,
    )
    embedder = SentenceTransformerEmbedder(
        settings.EMBEDDING_MODEL,
        dimension=settings.EMBEDDING_DIMENSION,
        batch_size=settings.EMBEDDING_BATCH_SIZE,
    )
    stores = {
        "pgvector": PgVectorStore(database.sessionmaker, dimension=settings.EMBEDDING_DIMENSION),
        "qdrant": qdrant,
    }
    try:
        await qdrant.ensure_ready()
        rows: list[dict[str, Any]] = []
        grouped: dict[str, list[float]] = defaultdict(list)
        for item in questions:
            vector = await asyncio.to_thread(embedder.embed, [item["question"]])
            hits = await stores[backend].search(
                [float(value) for value in vector[0]],
                top_k,
                SearchFilters(),
            )
            top_score = hits[0].score if hits else None
            grouped[item["group"]].append(top_score if top_score is not None else 0.0)
            rows.append(
                {
                    "id": item["id"],
                    "group": item["group"],
                    "question": item["question"],
                    "top1_score": round(top_score, 6) if top_score is not None else None,
                    "top1_chunk": (
                        {
                            "chunk_id": str(hits[0].chunk_id),
                            "filename": hits[0].filename,
                            "chunk_index": hits[0].chunk_index,
                            "page": hits[0].page,
                        }
                        if hits
                        else None
                    ),
                }
            )
        in_scores = grouped["in_corpus"]
        out_scores = grouped["out_of_corpus"]
        in_min = min(in_scores)
        out_max = max(out_scores)
        separable = out_max < in_min
        candidate = round((out_max + in_min) / 2, 6) if separable else None
        return {
            "backend": backend,
            "top_k": top_k,
            "questions": rows,
            "summary": {
                "in_corpus": _summary(in_scores),
                "out_of_corpus": _summary(out_scores),
                "separable": separable,
                "candidate_midpoint_threshold": candidate,
            },
        }
    finally:
        await qdrant.close()
        await database.dispose()


def _print_table(result: dict[str, Any]) -> None:
    print(f"\nBackend: {result['backend']} (top_k={result['top_k']})")
    print("| id | group | top-1 | top document |")
    print("| --- | --- | ---: | --- |")
    for row in result["questions"]:
        chunk = row["top1_chunk"]
        label = f"{chunk['filename']}#{chunk['chunk_index']}" if chunk else "none"
        print(f"| {row['id']} | {row['group']} | {row['top1_score']:.6f} | {label} |")
    print("\nSummary:")
    for group in ("in_corpus", "out_of_corpus"):
        summary = result["summary"][group]
        print(
            f"- {group}: n={summary['count']} min={summary['min']:.6f} "
            f"p50={summary['p50']:.6f} max={summary['max']:.6f} mean={summary['mean']:.6f}"
        )
    print(
        f"- separable={result['summary']['separable']} "
        f"candidate_midpoint={result['summary']['candidate_midpoint_threshold']}"
    )


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, default=Path("eval/abstention_probe.jsonl"))
    parser.add_argument("--backend", choices=("pgvector", "qdrant", "both"), default="both")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.top_k <= 50:
        raise SystemExit("--top-k must be between 1 and 50")

    questions = _load_questions(args.questions)
    backends: list[Backend] = (
        ["pgvector", "qdrant"] if args.backend == "both" else [cast(Backend, args.backend)]
    )
    results = [await _run(questions, backend, args.top_k) for backend in backends]
    for result in results:
        _print_table(result)
    if args.output:
        args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
