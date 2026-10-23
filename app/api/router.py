from fastapi import APIRouter

from app.api.routes import whoami

api_router = APIRouter(prefix="/v1")
api_router.include_router(whoami.router)
