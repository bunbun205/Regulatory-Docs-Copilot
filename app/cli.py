import argparse
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.security import Scope, generate_api_key, hash_api_key
from app.db.models import EMBEDDING_DIMENSION, ApiKey
from app.db.session import Database
from app.ingest.embedding import SentenceTransformerEmbedder
from app.ingest.pipeline import (
    IngestionConfig,
    IngestionJobError,
    IngestionPipeline,
    create_ingestion_job,
)
from app.store.pgvector_store import PgVectorStore
from app.store.qdrant_store import QdrantStore


async def _create_key(name: str, scope: Scope) -> int:
    database = Database(settings.DATABASE_URL)
    try:
        plaintext = generate_api_key()
        async with database.sessionmaker() as session:
            session.add(
                ApiKey(
                    name=name,
                    key_hash=hash_api_key(plaintext),
                    scope=scope.value,
                )
            )
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                print(
                    f"Error: an API key named {name!r} already exists.",
                    file=sys.stderr,
                )
                return 1
        print(plaintext)
        return 0
    finally:
        await database.dispose()


async def _ingest(manifest: Path, documents_dir: Path) -> int:
    database = Database(settings.DATABASE_URL)
    qdrant_store: QdrantStore | None = None
    try:
        if settings.EMBEDDING_DIMENSION != EMBEDDING_DIMENSION:
            print(
                "Error: LABDOCS_EMBEDDING_DIMENSION must match the database "
                f"vector dimension ({EMBEDDING_DIMENSION}).",
                file=sys.stderr,
            )
            return 1
        embedder = SentenceTransformerEmbedder(
            settings.EMBEDDING_MODEL,
            dimension=settings.EMBEDDING_DIMENSION,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
        )
        config = IngestionConfig(
            chunk_max_tokens=settings.CHUNK_MAX_TOKENS,
            chunk_overlap_tokens=settings.CHUNK_OVERLAP_TOKENS,
            embedding_batch_size=settings.EMBEDDING_BATCH_SIZE,
            max_file_bytes=settings.MAX_UPLOAD_BYTES,
        )
        if settings.VECTOR_BACKEND in {"qdrant", "both"}:
            qdrant_store = QdrantStore(
                settings.QDRANT_URL,
                settings.QDRANT_COLLECTION,
                dimension=settings.EMBEDDING_DIMENSION,
                api_key=settings.QDRANT_API_KEY,
                timeout=settings.QDRANT_TIMEOUT_SECONDS,
            )
            try:
                await qdrant_store.ensure_ready()
            except Exception as exc:
                print(
                    "Error: the configured Qdrant collection is unavailable or "
                    f"incompatible ({type(exc).__name__}).",
                    file=sys.stderr,
                )
                return 1
        job_id = await create_ingestion_job(database.sessionmaker)
        pipeline = IngestionPipeline(
            database.sessionmaker,
            embedder,
            config,
            (qdrant_store,) if qdrant_store is not None else (),
        )
        report = await pipeline.run_manifest_job(job_id, manifest, documents_dir)
        print(
            json.dumps(
                {"job_id": str(job_id), "status": "completed", "report": report},
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    except IngestionJobError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(
            f"Error: ingestion failed ({type(exc).__name__}). "
            "Inspect the ingestion job for details.",
            file=sys.stderr,
        )
        return 1
    finally:
        if qdrant_store is not None:
            await qdrant_store.close()
        await database.dispose()


async def _reindex_qdrant(
    pg_store: PgVectorStore,
    qdrant_store: QdrantStore,
) -> dict[str, object]:
    """Rebuild one Qdrant collection from the canonical Postgres chunks."""
    document_ids = await pg_store.document_ids()
    await qdrant_store.reset_collection()
    await qdrant_store.ensure_ready()

    indexed_documents = 0
    indexed_chunks = 0
    for document_id in document_ids:
        records = await pg_store.records_for_document(document_id)
        if not records:
            continue
        await qdrant_store.upsert(records)
        indexed_documents += 1
        indexed_chunks += len(records)
    return {
        "backend": "qdrant",
        "collection": qdrant_store.collection,
        "documents": indexed_documents,
        "chunks": indexed_chunks,
    }


async def _reindex(backend: str) -> int:
    if backend != "qdrant":
        print(f"Error: unsupported reindex backend {backend!r}.", file=sys.stderr)
        return 2
    if settings.EMBEDDING_DIMENSION != EMBEDDING_DIMENSION:
        print(
            "Error: LABDOCS_EMBEDDING_DIMENSION must match the database "
            f"vector dimension ({EMBEDDING_DIMENSION}).",
            file=sys.stderr,
        )
        return 1

    database = Database(settings.DATABASE_URL)
    qdrant_store = QdrantStore(
        settings.QDRANT_URL,
        settings.QDRANT_COLLECTION,
        dimension=settings.EMBEDDING_DIMENSION,
        api_key=settings.QDRANT_API_KEY,
        timeout=settings.QDRANT_TIMEOUT_SECONDS,
    )
    try:
        pg_store = PgVectorStore(
            database.sessionmaker,
            dimension=settings.EMBEDDING_DIMENSION,
        )
        summary = await _reindex_qdrant(pg_store, qdrant_store)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(
            f"Error: reindex failed ({type(exc).__name__}).",
            file=sys.stderr,
        )
        return 1
    finally:
        await qdrant_store.close()
        await database.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_key = subparsers.add_parser(
        "create-key",
        help="Create an API key and print the plaintext key once.",
    )
    create_key.add_argument("--name", required=True, help="Human-readable key name.")
    create_key.add_argument(
        "--scope",
        required=True,
        choices=[scope.value for scope in Scope],
        help="Key scope. A write key also has read access.",
    )

    ingest = subparsers.add_parser(
        "ingest",
        help="Ingest a manifest and its documents. Re-running is idempotent.",
    )
    ingest.add_argument("--manifest", required=True, type=Path)
    ingest.add_argument(
        "--documents-dir",
        type=Path,
        default=None,
        help="Directory containing the document files (defaults to the manifest directory).",
    )

    reindex = subparsers.add_parser(
        "reindex",
        help="Rebuild a vector backend from the canonical Postgres chunks.",
    )
    reindex.add_argument(
        "--backend",
        required=True,
        choices=["qdrant"],
        help="Backend to rebuild.",
    )

    args = parser.parse_args(argv)
    if args.command == "create-key":
        return asyncio.run(_create_key(args.name, Scope(args.scope)))
    if args.command == "ingest":
        documents_dir = args.documents_dir or args.manifest.parent
        return asyncio.run(_ingest(args.manifest, documents_dir))
    if args.command == "reindex":
        return asyncio.run(_reindex(args.backend))
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
