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
        job_id = await create_ingestion_job(database.sessionmaker)
        pipeline = IngestionPipeline(database.sessionmaker, embedder, config)
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

    args = parser.parse_args(argv)
    if args.command == "create-key":
        return asyncio.run(_create_key(args.name, Scope(args.scope)))
    if args.command == "ingest":
        documents_dir = args.documents_dir or args.manifest.parent
        return asyncio.run(_ingest(args.manifest, documents_dir))
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
