"""Reject oversized bodies before parsing, including chunked requests."""

import asyncio
from tempfile import SpooledTemporaryFile

from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.errors import error_response


class RequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def reject(status: int = 413) -> None:
            response = error_response(
                Request(scope),
                status,
                "payload_too_large" if status == 413 else "bad_request",
                "Request body exceeds the configured limit."
                if status == 413
                else "Invalid Content-Length header.",
            )
            await response(scope, receive, send)

        lengths = Headers(scope=scope).getlist("content-length")
        if lengths:
            if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
                await reject(400)
                return
            normalized = lengths[0].lstrip("0") or "0"
            if len(normalized) > len(str(self.max_bytes)) or int(normalized) > self.max_bytes:
                await reject()
                return

        # Bound memory and reject before a route handler can mutate state.
        # Declared lengths are never trusted alone.
        with SpooledTemporaryFile(max_size=1024 * 1024) as body:
            size = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                size += len(chunk)
                if size > self.max_bytes:
                    await reject()
                    return
                await asyncio.to_thread(body.write, chunk)
                if not message.get("more_body", False):
                    break
            await asyncio.to_thread(body.seek, 0)
            remaining = size
            replayed = False

            async def replay() -> Message:
                nonlocal remaining, replayed
                if replayed:
                    return await receive()
                data = await asyncio.to_thread(body.read, 64 * 1024)
                remaining -= len(data)
                replayed = remaining == 0
                return {"type": "http.request", "body": data, "more_body": not replayed}

            await self.app(scope, replay, send)
