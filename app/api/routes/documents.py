import asyncio
import hashlib
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Query,
    Request,
    UploadFile,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_scope
from app.api.errors import APIError
from app.api.schemas import (
    DocumentDetail,
    DocumentListResponse,
    DocumentSummary,
    UploadResponse,
)
from app.core.security import Scope
from app.db.models import ApiKey, Chunk, Document
from app.db.session import get_session
from app.ingest.extract import SUPPORTED_EXTENSIONS
from app.ingest.pipeline import (
    DocumentMetadata,
    create_ingestion_job,
    run_upload_job_background,
)

router = APIRouter(tags=["documents"])


@router.post("/documents", response_model=UploadResponse, status_code=202)
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form(min_length=1, max_length=500)],
    source_agency: Annotated[str, Form(min_length=1, max_length=200)],
    doc_type: Annotated[str, Form(min_length=1, max_length=100)],
    year: Annotated[int, Form(ge=1900, le=2100)],
    version: Annotated[str, Form(min_length=1, max_length=200)],
    _key: Annotated[ApiKey, Depends(require_scope(Scope.WRITE))],
) -> UploadResponse:
    """Accept one document and schedule ingestion as a background job."""
    filename = Path(file.filename or "").name
    if not filename:
        raise APIError(422, "validation_error", "A file name is required.")
    if len(filename) > 512:
        raise APIError(422, "validation_error", "File name is too long.")

    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise APIError(
            422,
            "invalid_file_type",
            f"Unsupported file type. Allowed extensions: {allowed}.",
        )

    metadata = DocumentMetadata(
        filename=filename,
        title=_required_text(title, "title"),
        source_agency=_required_text(source_agency, "source_agency"),
        doc_type=_required_text(doc_type, "doc_type"),
        year=year,
        version=_required_text(version, "version"),
    )

    config = request.app.state.ingestion_config
    contents = bytearray()
    while chunk := await file.read(1024 * 1024):
        if len(contents) + len(chunk) > config.max_file_bytes:
            raise APIError(413, "payload_too_large", "Uploaded file is too large.")
        contents.extend(chunk)
    if not contents:
        raise APIError(422, "validation_error", "Uploaded file is empty.")

    digest = hashlib.sha256(contents).hexdigest()
    upload_dir: Path = request.app.state.upload_dir
    await asyncio.to_thread(upload_dir.mkdir, parents=True, exist_ok=True)
    stored_path = upload_dir / f"{digest}{suffix}"
    if not stored_path.exists():
        await asyncio.to_thread(stored_path.write_bytes, bytes(contents))

    job_id = await create_ingestion_job(request.app.state.sessionmaker)
    background_tasks.add_task(
        run_upload_job_background,
        request.app.state.sessionmaker,
        request.app.state.embedder,
        request.app.state.ingestion_config,
        job_id,
        stored_path,
        metadata,
    )
    return UploadResponse(job_id=job_id)


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    _key: Annotated[ApiKey, Depends(require_scope(Scope.READ))],
    session: Annotated[AsyncSession, Depends(get_session)],
    doc_type: Annotated[str | None, Query()] = None,
    source_agency: Annotated[str | None, Query()] = None,
    year_min: Annotated[int | None, Query(ge=1900, le=2100)] = None,
    year_max: Annotated[int | None, Query(ge=1900, le=2100)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DocumentListResponse:
    """List document metadata with the filters used by the UI."""
    if year_min is not None and year_max is not None and year_min > year_max:
        raise APIError(422, "validation_error", "year_min must be less than or equal to year_max.")

    filters: list[Any] = []
    if doc_type is not None:
        filters.append(Document.doc_type == doc_type)
    if source_agency is not None:
        filters.append(Document.source_agency == source_agency)
    if year_min is not None:
        filters.append(Document.year >= year_min)
    if year_max is not None:
        filters.append(Document.year <= year_max)

    total = int(
        await session.scalar(select(func.count()).select_from(Document).where(*filters)) or 0
    )
    documents = (
        await session.scalars(
            select(Document)
            .where(*filters)
            .order_by(Document.created_at.desc(), Document.filename)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return DocumentListResponse(
        items=[DocumentSummary.model_validate(document) for document in documents],
        total=total,
    )


@router.get("/documents/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: UUID,
    _key: Annotated[ApiKey, Depends(require_scope(Scope.READ))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DocumentDetail:
    """Return one document's metadata and chunk count."""
    document = await session.get(Document, document_id)
    if document is None:
        raise APIError(404, "not_found", "Document not found.")
    chunk_count = int(
        await session.scalar(
            select(func.count()).select_from(Chunk).where(Chunk.document_id == document_id)
        )
        or 0
    )
    summary = DocumentSummary.model_validate(document)
    return DocumentDetail(**summary.model_dump(), chunk_count=chunk_count)


def _required_text(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise APIError(422, "validation_error", f"{field_name} must not be blank.")
    return cleaned
