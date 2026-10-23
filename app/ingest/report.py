from typing import Any

import pandas as pd


def chunk_length_stats(token_counts: list[int]) -> dict[str, int | float | None]:
    """Summarize chunk token lengths via a small Pandas DataFrame."""
    frame = pd.DataFrame({"token_count": token_counts})
    if frame.empty:
        return {
            "count": 0,
            "min": None,
            "p50": None,
            "p90": None,
            "max": None,
            "mean": None,
        }
    series = frame["token_count"]
    return {
        "count": int(series.count()),
        "min": int(series.min()),
        "p50": float(series.quantile(0.5)),
        "p90": float(series.quantile(0.9)),
        "max": int(series.max()),
        "mean": float(series.mean()),
    }


def build_report(
    *,
    documents_total: int,
    documents: list[dict[str, Any]],
    duplicates: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    rejected_rows: list[dict[str, Any]],
    token_counts: list[int],
    duration_ms: float,
) -> dict[str, Any]:
    return {
        "documents_total": documents_total,
        "documents_ingested": len(documents),
        "documents_duplicate": len(duplicates),
        "documents_failed": len(failures),
        "chunks": sum(int(document["chunks"]) for document in documents),
        "chunk_length": chunk_length_stats(token_counts),
        "documents": documents,
        "duplicates": duplicates,
        "failures": failures,
        "rejected_rows": rejected_rows,
        "duration_ms": round(duration_ms, 2),
    }
