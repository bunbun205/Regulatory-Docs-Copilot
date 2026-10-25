from fastapi import APIRouter

from app.api.routes import agent, ask, documents, jobs, search, whoami

api_router = APIRouter(prefix="/v1")
api_router.include_router(whoami.router)
api_router.include_router(documents.router)
api_router.include_router(jobs.router)
api_router.include_router(search.router)
api_router.include_router(ask.router)
api_router.include_router(agent.router)
