import asyncio
from pathlib import Path
from typing import Annotated, Literal, cast
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Request,
    UploadFile,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_scope
from app.api.errors import APIError
from app.api.schemas import (
    GapCheckCancelResponse,
    GapCheckJobResponse,
    GapCheckProgress,
    GapCheckReport,
    GapCheckSubmitResponse,
)
from app.core.config import settings
from app.core.security import Scope
from app.db.models import ApiKey, GapCheckJob
from app.db.session import get_session
from app.gapcheck.jobs import (
    GapCheckLimitError,
    config_from_settings,
    create_gapcheck_job,
    run_gapcheck_job_background,
)
from app.gapcheck.segment import (
    ClauseCapExceeded,
    GapCheckInputError,
    segment_sop,
)
from app.ingest.extract import SUPPORTED_EXTENSIONS, ExtractionError, extract_document
from app.rag.retriever import Backend
from app.store.base import SearchFilters

router = APIRouter(tags=["gapcheck"])


@router.post("/gapcheck", response_model=GapCheckSubmitResponse, status_code=202)
async def submit_gapcheck(
    request: Request,
    background_tasks: BackgroundTasks,
    key: Annotated[ApiKey, Depends(require_scope(Scope.READ))],
    session: Annotated[AsyncSession, Depends(get_session)],
    file: Annotated[UploadFile | None, File()] = None,
    text: Annotated[str | None, Form()] = None,
    doc_type: Annotated[str | None, Form()] = None,
    source_agency: Annotated[str | None, Form()] = None,
    year_min: Annotated[int | None, Form(ge=1900, le=2100)] = None,
    year_max: Annotated[int | None, Form(ge=1900, le=2100)] = None,
    backend: Annotated[Literal["pgvector", "qdrant"] | None, Form()] = None,
) -> GapCheckSubmitResponse:
    """Submit an SOP file or pasted text and enqueue a two-direction gap check."""
    has_file = file is not None and bool(file.filename)
    has_text = text is not None and bool(text.strip())
    if has_file == has_text:
        raise APIError(
            422,
            "validation_error",
            "Provide exactly one of an SOP file or pasted SOP text.",
        )

    sop_text = (
        await _extract_uploaded_sop(file, request.app.state.upload_dir)
        if has_file and file is not None
        else (text or "").strip()
    )
    if len(sop_text) > settings.GAPCHECK_MAX_SOP_CHARS:
        raise APIError(
            413,
            "payload_too_large",
            f"SOP text exceeds the {settings.GAPCHECK_MAX_SOP_CHARS}-character limit.",
        )
    try:
        segment_sop(sop_text, max_clauses=settings.GAPCHECK_MAX_CLAUSES)
    except ClauseCapExceeded as exc:
        raise APIError(422, "clause_cap_exceeded", str(exc)) from exc
    except GapCheckInputError as exc:
        raise APIError(422, "invalid_sop", str(exc)) from exc

    try:
        filters = SearchFilters(
            doc_type=_optional_text(doc_type),
            source_agency=_optional_text(source_agency),
            year_min=year_min,
            year_max=year_max,
        )
    except ValueError as exc:
        raise APIError(422, "validation_error", str(exc)) from exc

    default_backend = getattr(request.app.state, "default_vector_backend", "pgvector")
    backend_value = backend or default_backend
    stores = getattr(request.app.state, "vector_stores", {})
    if backend_value not in stores:
        raise APIError(
            422,
            "backend_unavailable",
            f"Vector backend {backend_value!r} is not configured.",
        )
    selected_backend = cast(Literal["pgvector", "qdrant"], backend_value)

    active = int(
        await session.scalar(
            select(func.count())
            .select_from(GapCheckJob)
            .where(
                GapCheckJob.api_key_id == key.id,
                GapCheckJob.status.in_(("queued", "running")),
            )
        )
        or 0
    )
    if active >= settings.GAPCHECK_MAX_CONCURRENT_JOBS_PER_KEY:
        raise APIError(
            429,
            "gapcheck_limit",
            "This API key already has the maximum number of active gap checks.",
            headers={"Retry-After": "30"},
        )

    try:
        job_id = await create_gapcheck_job(request.app.state.sessionmaker, key.id)
    except GapCheckLimitError as exc:
        raise APIError(
            429,
            "gapcheck_limit",
            "This API key already has the maximum number of active gap checks.",
            headers={"Retry-After": "30"},
        ) from exc
    background_tasks.add_task(
        run_gapcheck_job_background,
        request.app.state.sessionmaker,
        request.app.state.embedder,
        request.app.state.llm_client,
        request.app.state.vector_stores,
        cast(Backend, default_backend),
        config_from_settings(settings),
        job_id,
        sop_text,
        filters,
        cast(Backend, selected_backend),
        f"{settings.LLM_PROVIDER}:{settings.LLM_MODEL}",
    )
    return GapCheckSubmitResponse(job_id=job_id)


@router.get("/gapcheck/{job_id}", response_model=GapCheckJobResponse)
async def get_gapcheck(
    job_id: UUID,
    key: Annotated[ApiKey, Depends(require_scope(Scope.READ))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GapCheckJobResponse:
    """Return gap-check progress, and the report once the run is complete."""
    job = await session.get(GapCheckJob, job_id)
    if job is None or job.api_key_id != key.id:
        raise APIError(404, "not_found", "Gap check not found.")
    return _job_response(job)


@router.post("/gapcheck/{job_id}/cancel", response_model=GapCheckCancelResponse, status_code=202)
async def cancel_gapcheck(
    job_id: UUID,
    key: Annotated[ApiKey, Depends(require_scope(Scope.READ))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GapCheckCancelResponse:
    """Request cooperative cancellation; the runner stops between bounded steps."""
    job = await session.get(GapCheckJob, job_id)
    if job is None or job.api_key_id != key.id:
        raise APIError(404, "not_found", "Gap check not found.")
    if job.status in {"queued", "running"}:
        job.cancel_requested = True
        await session.commit()
    return GapCheckCancelResponse(job_id=job.id, cancel_requested=job.cancel_requested)


def _job_response(job: GapCheckJob) -> GapCheckJobResponse:
    return GapCheckJobResponse(
        id=job.id,
        status=cast(
            Literal["queued", "running", "completed", "failed", "cancelled"],
            job.status,
        ),
        progress=GapCheckProgress.model_validate(job.progress or {}),
        report=GapCheckReport.model_validate(job.report) if job.report else None,
        error=job.error,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


async def _extract_uploaded_sop(file: UploadFile, upload_dir: Path) -> str:
    filename = Path(file.filename or "").name
    if not filename:
        raise APIError(422, "validation_error", "A file name is required.")
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise APIError(
            422,
            "invalid_file_type",
            f"Unsupported file type. Allowed extensions: {allowed}.",
        )

    contents = bytearray()
    while chunk := await file.read(1024 * 1024):
        if len(contents) + len(chunk) > settings.MAX_UPLOAD_BYTES:
            raise APIError(413, "payload_too_large", "Uploaded file is too large.")
        contents.extend(chunk)
    if not contents:
        raise APIError(422, "validation_error", "Uploaded file is empty.")

    await asyncio.to_thread(upload_dir.mkdir, parents=True, exist_ok=True)
    temp_path = upload_dir / f"gapcheck-{uuid4().hex}{suffix}"
    await asyncio.to_thread(temp_path.write_bytes, bytes(contents))
    try:
        extracted = await asyncio.to_thread(extract_document, temp_path)
    except ExtractionError as exc:
        raise APIError(422, "invalid_sop", str(exc)) from exc
    finally:
        await asyncio.to_thread(temp_path.unlink, missing_ok=True)
    return "\n\n".join(block.text for block in extracted.blocks)


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None
