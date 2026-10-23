from fastapi import APIRouter

from app.api.routes import documents, jobs, whoami

api_router = APIRouter(prefix="/v1")
api_router.include_router(whoami.router)
api_router.include_router(documents.router)
api_router.include_router(jobs.router)
