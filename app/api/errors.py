from collections.abc import Mapping

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.middleware import REQUEST_ID_HEADER

_STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    502: "upstream_error",
    503: "service_unavailable",
}


class APIError(Exception):
    """An expected API failure rendered with the standard error envelope."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    request_id = _request_id(request)
    response = JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
            }
        },
        headers=headers,
    )
    response.headers[REQUEST_ID_HEADER] = request_id
    return response


async def api_error_handler(request: Request, exc: Exception) -> Response:
    if not isinstance(exc, APIError):
        return await unhandled_exception_handler(request, exc)
    return error_response(request, exc.status_code, exc.code, exc.message, exc.headers)


async def http_exception_handler(request: Request, exc: Exception) -> Response:
    if not isinstance(exc, StarletteHTTPException):
        return await unhandled_exception_handler(request, exc)
    message = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return error_response(
        request,
        exc.status_code,
        _STATUS_CODES.get(exc.status_code, "error"),
        message,
        exc.headers,
    )


async def validation_error_handler(request: Request, exc: Exception) -> Response:
    if not isinstance(exc, RequestValidationError):
        return await unhandled_exception_handler(request, exc)
    return error_response(request, 422, "validation_error", "Request validation failed.")


async def unhandled_exception_handler(request: Request, exc: Exception) -> Response:
    structlog.get_logger("labdocs.error").error(
        "request.unhandled",
        error_type=type(exc).__name__,
    )
    return error_response(request, 500, "internal_error", "An internal error occurred.")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
