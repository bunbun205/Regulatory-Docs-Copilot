from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.api.errors import register_exception_handlers
from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.db.session import Database

configure_logging(settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    database = Database(settings.DATABASE_URL)
    application.state.database = database
    application.state.sessionmaker = database.sessionmaker
    try:
        yield
    finally:
        await database.dispose()


def create_app() -> FastAPI:
    application = FastAPI(
        title="labdocs",
        version="0.1.0",
        description=(
            "Regulatory Docs Copilot: RAG, agentic search and compliance gap "
            "checking for regulatory and lab-safety documents."
        ),
        lifespan=lifespan,
    )
    application.add_middleware(RequestContextMiddleware)
    register_exception_handlers(application)
    application.include_router(api_router)

    @application.get("/healthz", tags=["health"])
    async def healthz() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "ok"}

    @application.get("/readyz", tags=["health"])
    async def readyz(request: Request) -> JSONResponse:
        """Readiness probe: the database must answer. Store/embedder checks follow."""
        try:
            sessionmaker = request.app.state.sessionmaker
            async with sessionmaker() as session:
                await session.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse(
                status_code=503,
                content={"status": "error", "checks": {"database": "unavailable"}},
            )
        return JSONResponse(content={"status": "ok", "checks": {"database": "ok"}})

    @application.get("/metrics", tags=["health"])
    async def metrics() -> Response:
        """Prometheus scrape endpoint."""
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return application


app = create_app()
