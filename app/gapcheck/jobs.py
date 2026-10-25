"""Job creation, progress persistence and background execution for gap checks."""

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.models import GapCheckJob
from app.gapcheck.judge import GapCheckJudge
from app.gapcheck.runner import (
    GapCheckCancelled,
    GapCheckConfig,
    GapCheckError,
    GapCheckRunner,
)
from app.gapcheck.segment import GapCheckInputError
from app.ingest.embedding import Embedder
from app.llm.base import LLMClient
from app.rag.retriever import Backend, Retriever
from app.store.base import SearchFilters, VectorStore

logger = structlog.get_logger("labdocs.gapcheck.jobs")


class GapCheckLimitError(Exception):
    """The API key already has an active gap-check job."""


def config_from_settings(settings: Settings) -> GapCheckConfig:
    return GapCheckConfig(
        max_clauses=settings.GAPCHECK_MAX_CLAUSES,
        max_requirements=settings.GAPCHECK_MAX_REQUIREMENTS,
        max_tokens=settings.GAPCHECK_MAX_TOKENS,
        retrieval_top_k=settings.GAPCHECK_RETRIEVAL_TOP_K,
        relevance_threshold=settings.GAPCHECK_RELEVANCE_THRESHOLD,
        global_top_documents=settings.GAPCHECK_GLOBAL_TOP_DOCUMENTS,
        sop_match_top_k=settings.GAPCHECK_SOP_MATCH_TOP_K,
        judge_concurrency=settings.GAPCHECK_JUDGE_CONCURRENCY,
        retrieval_concurrency=settings.GAPCHECK_RETRIEVAL_CONCURRENCY,
        judge_max_tokens=settings.GAPCHECK_JUDGE_MAX_TOKENS,
    )


async def create_gapcheck_job(
    sessionmaker: async_sessionmaker[AsyncSession],
    api_key_id: uuid.UUID,
) -> uuid.UUID:
    job_id = uuid.uuid4()
    async with sessionmaker() as session:
        session.add(
            GapCheckJob(
                id=job_id,
                api_key_id=api_key_id,
                status="queued",
                progress={
                    "phase": "queued",
                    "clauses_total": 0,
                    "clauses_done": 0,
                    "requirements_total": 0,
                    "requirements_done": 0,
                },
            )
        )
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise GapCheckLimitError from exc
    return job_id


async def update_gapcheck_progress(
    sessionmaker: async_sessionmaker[AsyncSession],
    job_id: uuid.UUID,
    progress: dict[str, Any],
) -> None:
    async with sessionmaker() as session:
        job = await session.get(GapCheckJob, job_id)
        if job is None:
            return
        job.progress = dict(progress)
        await session.commit()


async def is_gapcheck_cancel_requested(
    sessionmaker: async_sessionmaker[AsyncSession],
    job_id: uuid.UUID,
) -> bool:
    async with sessionmaker() as session:
        requested = await session.scalar(
            select(GapCheckJob.cancel_requested).where(GapCheckJob.id == job_id)
        )
    return bool(requested)


async def run_gapcheck_job_background(
    sessionmaker: async_sessionmaker[AsyncSession],
    embedder: Embedder,
    llm_client: LLMClient,
    vector_stores: Mapping[str, VectorStore],
    default_backend: Backend,
    config: GapCheckConfig,
    job_id: uuid.UUID,
    sop_text: str,
    filters: SearchFilters,
    backend: Backend,
    model_label: str,
) -> None:
    """Run one gap check without ever logging the SOP content."""
    async with sessionmaker() as session:
        job = await session.get(GapCheckJob, job_id)
        if job is None:
            return
        if job.cancel_requested:
            job.status = "cancelled"
            job.error = "Gap check cancelled."
            job.finished_at = datetime.now(UTC)
            job.progress = {**dict(job.progress or {}), "phase": "cancelled"}
            await session.commit()
            return
        job.status = "running"
        job.started_at = datetime.now(UTC)
        job.progress = {**dict(job.progress or {}), "phase": "clauses"}
        await session.commit()

    retriever = Retriever(embedder, vector_stores, default_backend)
    judge = GapCheckJudge(
        llm_client,
        sessionmaker,
        namespace=f"gapcheck:{model_label}",
        max_tokens=config.judge_max_tokens,
    )
    runner = GapCheckRunner(
        retriever,
        embedder,
        judge,
        config,
        job_id=str(job_id),
        model_label=model_label,
        progress_callback=lambda progress: update_gapcheck_progress(sessionmaker, job_id, progress),
        cancel_check=lambda: is_gapcheck_cancel_requested(sessionmaker, job_id),
    )
    try:
        report = await runner.run(sop_text, filters=filters, backend=backend)
    except GapCheckCancelled:
        await _finish_job(
            sessionmaker,
            job_id,
            status="cancelled",
            error="Gap check cancelled.",
            progress={"phase": "cancelled"},
        )
        return
    except (GapCheckInputError, GapCheckError) as exc:
        await _finish_job(
            sessionmaker,
            job_id,
            status="failed",
            error=str(exc),
            progress={"phase": "failed"},
        )
        return
    except Exception as exc:
        logger.error("gapcheck.job_failed", job_id=str(job_id), error_type=type(exc).__name__)
        await _finish_job(
            sessionmaker,
            job_id,
            status="failed",
            error="Gap check failed.",
            progress={"phase": "failed"},
        )
        return

    metadata = report.get("metadata", {})
    await _finish_job(
        sessionmaker,
        job_id,
        status="completed",
        report=report,
        progress={
            "phase": "completed",
            "clauses_total": metadata.get("clauses_total", 0),
            "clauses_done": metadata.get("clauses_total", 0),
            "requirements_total": metadata.get("requirements_total", 0),
            "requirements_done": metadata.get("requirements_total", 0),
        },
    )


async def _finish_job(
    sessionmaker: async_sessionmaker[AsyncSession],
    job_id: uuid.UUID,
    *,
    status: str,
    progress: dict[str, Any],
    error: str | None = None,
    report: dict[str, Any] | None = None,
) -> None:
    async with sessionmaker() as session:
        job = await session.get(GapCheckJob, job_id)
        if job is None:
            return
        job.status = status
        job.error = error
        job.report = report
        job.finished_at = datetime.now(UTC)
        job.progress = {**dict(job.progress or {}), **progress}
        await session.commit()
