from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.core.config import settings
from app.core.logging import configure_logging

configure_logging(settings.LOG_LEVEL)

app = FastAPI(
    title="labdocs",
    version="0.1.0",
    description=(
        "Regulatory Docs Copilot: RAG, agentic search and compliance gap "
        "checking for regulatory and lab-safety documents."
    ),
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    """Readiness probe (dependency checks land with the DB/store milestones)."""
    return {"status": "ok"}


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus scrape endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
