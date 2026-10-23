from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_scope
from app.api.errors import APIError
from app.api.schemas import IngestionJobResponse
from app.core.security import Scope
from app.db.models import ApiKey, IngestionJob
from app.db.session import get_session

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}", response_model=IngestionJobResponse)
async def get_ingestion_job(
    job_id: UUID,
    _key: Annotated[ApiKey, Depends(require_scope(Scope.READ))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IngestionJobResponse:
    """Return ingestion status and the report when the job is terminal."""
    job = await session.get(IngestionJob, job_id)
    if job is None:
        raise APIError(404, "not_found", "Ingestion job not found.")
    return IngestionJobResponse.model_validate(job)
