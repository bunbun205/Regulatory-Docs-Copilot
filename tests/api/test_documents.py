import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from fastapi import FastAPI
from httpx import AsyncClient

from app.core.security import Scope
from app.ingest.pipeline import IngestionConfig
from tests.helpers import FakeEmbedder


async def _upload(
    client: AsyncClient,
    key: str,
    *,
    filename: str = "synthetic-note.txt",
    content: bytes = b"Synthetic note for the API test.",
    title: str = "Synthetic Note",
    source_agency: str = "Synthetic Agency",
    doc_type: str = "guidance",
    year: str = "2024",
    version: str = "v1",
) -> Any:
    return await client.post(
        "/v1/documents",
        headers={"X-API-Key": key},
        files={"file": (filename, content, "text/plain")},
        data={
            "title": title,
            "source_agency": source_agency,
            "doc_type": doc_type,
            "year": year,
            "version": version,
        },
    )


async def _wait_for_job(client: AsyncClient, key: str, job_id: str) -> dict[str, Any]:
    for _ in range(500):
        response = await client.get(f"/v1/jobs/{job_id}", headers={"X-API-Key": key})
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed"}:
            return payload
        await asyncio.sleep(0.01)
    raise AssertionError(f"Job {job_id} did not finish in time.")


async def test_upload_ingests_document_and_job_is_visible(
    client: AsyncClient,
    make_api_key: Callable[..., Awaitable[str]],
    fake_embedder: FakeEmbedder,
) -> None:
    writer = await make_api_key(name="uploader", scope=Scope.WRITE)
    reader = await make_api_key(name="upload-reader", scope=Scope.READ)
    content = b"Synthetic note for the API test.\n\nA second synthetic paragraph."

    response = await _upload(client, writer, content=content)
    assert response.status_code == 202
    upload = response.json()
    assert upload["status"] == "queued"
    job = await _wait_for_job(client, reader, upload["job_id"])

    assert job["status"] == "completed"
    assert job["error"] is None
    assert job["report"]["documents_total"] == 1
    assert job["report"]["documents_ingested"] == 1
    assert job["report"]["documents_duplicate"] == 0
    assert job["report"]["chunks"] == 1
    assert job["started_at"] is not None
    assert job["finished_at"] is not None
    assert fake_embedder.calls == 1

    listing = await client.get("/v1/documents", headers={"X-API-Key": reader})
    assert listing.status_code == 200
    listed = listing.json()
    assert listed["total"] == 1
    assert listed["items"][0]["filename"] == "synthetic-note.txt"
    assert listed["items"][0]["title"] == "Synthetic Note"
    assert listed["items"][0]["doc_type"] == "guidance"

    document_id = listed["items"][0]["id"]
    detail = await client.get(
        f"/v1/documents/{document_id}",
        headers={"X-API-Key": reader},
    )
    assert detail.status_code == 200
    assert detail.json()["chunk_count"] == 1

    by_type = await client.get(
        "/v1/documents",
        params={"doc_type": "guidance"},
        headers={"X-API-Key": reader},
    )
    assert by_type.json()["total"] == 1
    no_match = await client.get(
        "/v1/documents",
        params={"doc_type": "regulation"},
        headers={"X-API-Key": reader},
    )
    assert no_match.json()["total"] == 0
    by_year = await client.get(
        "/v1/documents",
        params={"year_min": "2024", "year_max": "2024"},
        headers={"X-API-Key": reader},
    )
    assert by_year.json()["total"] == 1

    duplicate = await _upload(
        client,
        writer,
        content=content,
        title="Different metadata for duplicate bytes",
    )
    assert duplicate.status_code == 202
    duplicate_job = await _wait_for_job(client, reader, duplicate.json()["job_id"])
    assert duplicate_job["status"] == "completed"
    assert duplicate_job["report"]["documents_ingested"] == 0
    assert duplicate_job["report"]["documents_duplicate"] == 1
    assert duplicate_job["report"]["chunks"] == 0
    assert fake_embedder.calls == 1

    after_duplicate = await client.get("/v1/documents", headers={"X-API-Key": reader})
    assert after_duplicate.json()["total"] == 1


async def test_upload_requires_write_scope(
    client: AsyncClient,
    make_api_key: Callable[..., Awaitable[str]],
) -> None:
    reader = await make_api_key(name="read-upload", scope=Scope.READ)
    forbidden = await _upload(client, reader)
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "forbidden"

    missing = await client.post(
        "/v1/documents",
        files={"file": ("note.txt", b"content", "text/plain")},
        data={
            "title": "Note",
            "source_agency": "Synthetic Agency",
            "doc_type": "guidance",
            "year": "2024",
            "version": "v1",
        },
    )
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "unauthorized"


async def test_upload_rejects_invalid_inputs(
    client: AsyncClient,
    app: FastAPI,
    make_api_key: Callable[..., Awaitable[str]],
) -> None:
    writer = await make_api_key(name="invalid-uploader", scope=Scope.WRITE)

    unsupported = await _upload(client, writer, filename="table.csv", content=b"a,b\n")
    assert unsupported.status_code == 422
    assert unsupported.json()["error"]["code"] == "invalid_file_type"

    empty = await _upload(client, writer, content=b"")
    assert empty.status_code == 422
    assert empty.json()["error"]["code"] == "validation_error"

    blank = await _upload(client, writer, title="   ")
    assert blank.status_code == 422
    assert blank.json()["error"]["code"] == "validation_error"

    app.state.ingestion_config = IngestionConfig(max_file_bytes=10)
    oversized = await _upload(client, writer, content=b"x" * 11)
    assert oversized.status_code == 413
    assert oversized.json()["error"]["code"] == "payload_too_large"


async def test_invalid_pdf_upload_marks_job_failed(
    client: AsyncClient,
    make_api_key: Callable[..., Awaitable[str]],
) -> None:
    writer = await make_api_key(name="broken-pdf-uploader", scope=Scope.WRITE)
    reader = await make_api_key(name="broken-pdf-reader", scope=Scope.READ)

    response = await _upload(
        client,
        writer,
        filename="broken.pdf",
        content=b"not a pdf",
    )
    assert response.status_code == 202
    job = await _wait_for_job(client, reader, response.json()["job_id"])

    assert job["status"] == "failed"
    assert job["report"] is None
    assert job["error"] is not None
    assert "PDF" in job["error"]

    listing = await client.get("/v1/documents", headers={"X-API-Key": reader})
    assert listing.json()["total"] == 0


async def test_document_and_job_not_found(
    client: AsyncClient,
    make_api_key: Callable[..., Awaitable[str]],
) -> None:
    reader = await make_api_key(name="not-found-reader", scope=Scope.READ)
    missing_id = str(uuid4())

    document = await client.get(
        f"/v1/documents/{missing_id}",
        headers={"X-API-Key": reader},
    )
    assert document.status_code == 404
    assert document.json()["error"]["code"] == "not_found"

    job = await client.get(
        f"/v1/jobs/{missing_id}",
        headers={"X-API-Key": reader},
    )
    assert job.status_code == 404
    assert job.json()["error"]["code"] == "not_found"

    invalid = await client.get(
        "/v1/documents/not-a-uuid",
        headers={"X-API-Key": reader},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"
