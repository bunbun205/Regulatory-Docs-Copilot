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
from app.db.models import EMBEDDING_DIMENSION
from app.db.session import Database
from app.ingest.embedding import SentenceTransformerEmbedder
from app.ingest.pipeline import IngestionConfig
from app.store.base import VectorStore
from app.store.pgvector_store import PgVectorStore, ensure_iterative_scan_supported
from app.store.qdrant_store import QdrantStore

configure_logging(settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    if settings.EMBEDDING_DIMENSION != EMBEDDING_DIMENSION:
        raise RuntimeError(
            "LABDOCS_EMBEDDING_DIMENSION must match the database vector dimension "
            f"({EMBEDDING_DIMENSION}). Create a migration before changing it."
        )
    embedder = SentenceTransformerEmbedder(
        settings.EMBEDDING_MODEL,
        dimension=settings.EMBEDDING_DIMENSION,
        batch_size=settings.EMBEDDING_BATCH_SIZE,
    )
    if embedder.dimension != EMBEDDING_DIMENSION:
        raise RuntimeError(
            f"Embedder dimension must match the database vector dimension ({EMBEDDING_DIMENSION})."
        )
    database = Database(settings.DATABASE_URL)
    try:
        await ensure_iterative_scan_supported(database.sessionmaker)
    except Exception:
        await database.dispose()
        raise
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    application.state.database = database
    application.state.sessionmaker = database.sessionmaker
    application.state.upload_dir = settings.UPLOAD_DIR
    application.state.embedder = embedder
    application.state.ingestion_config = IngestionConfig(
        chunk_max_tokens=settings.CHUNK_MAX_TOKENS,
        chunk_overlap_tokens=settings.CHUNK_OVERLAP_TOKENS,
        embedding_batch_size=settings.EMBEDDING_BATCH_SIZE,
        max_file_bytes=settings.MAX_UPLOAD_BYTES,
    )
    pg_store = PgVectorStore(
        database.sessionmaker,
        dimension=settings.EMBEDDING_DIMENSION,
    )
    vector_stores: dict[str, VectorStore] = {"pgvector": pg_store}
    qdrant_store: QdrantStore | None = None
    if settings.VECTOR_BACKEND in {"qdrant", "both"}:
        qdrant_store = QdrantStore(
            settings.QDRANT_URL,
            settings.QDRANT_COLLECTION,
            dimension=settings.EMBEDDING_DIMENSION,
            api_key=settings.QDRANT_API_KEY,
            timeout=settings.QDRANT_TIMEOUT_SECONDS,
        )
        vector_stores["qdrant"] = qdrant_store
        try:
            await qdrant_store.ensure_ready()
        except Exception:
            await qdrant_store.close()
            await database.dispose()
            raise
    application.state.vector_stores = vector_stores
    application.state.default_vector_backend = (
        "qdrant" if settings.VECTOR_BACKEND == "qdrant" else "pgvector"
    )
    application.state.ingestion_vector_stores = (qdrant_store,) if qdrant_store is not None else ()
    try:
        yield
    finally:
        if qdrant_store is not None:
            await qdrant_store.close()
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
        """Readiness probe: the database and configured vector backend must answer."""
        checks: dict[str, str] = {}
        try:
            sessionmaker = request.app.state.sessionmaker
            async with sessionmaker() as session:
                await session.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception:
            return JSONResponse(
                status_code=503,
                content={"status": "error", "checks": {"database": "unavailable"}},
            )

        qdrant_store = getattr(request.app.state, "vector_stores", {}).get("qdrant")
        if qdrant_store is not None:
            try:
                await qdrant_store.health()
                checks["qdrant"] = "ok"
            except Exception:
                checks["qdrant"] = "unavailable"
                return JSONResponse(
                    status_code=503,
                    content={"status": "error", "checks": checks},
                )
        return JSONResponse(content={"status": "ok", "checks": checks})

    @application.get("/metrics", tags=["health"])
    async def metrics() -> Response:
        """Prometheus scrape endpoint."""
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return application


app = create_app()
