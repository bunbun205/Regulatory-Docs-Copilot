from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import APIError
from app.core.rate_limit import RateLimiter
from app.core.security import Scope, has_scope, hash_api_key
from app.db.models import ApiKey
from app.db.session import get_session

api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="API key created with `python -m app.cli create-key`.",
)


async def get_current_api_key(
    request: Request,
    api_key: Annotated[str | None, Security(api_key_header)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiKey:
    """Resolve the presented API key to a stored key, or fail with 401."""
    if not api_key:
        raise APIError(401, "unauthorized", "Missing API key.")
    stored = await session.scalar(select(ApiKey).where(ApiKey.key_hash == hash_api_key(api_key)))
    if stored is None:
        raise APIError(401, "unauthorized", "Invalid API key.")
    limiter: RateLimiter = request.app.state.rate_limiter
    result = limiter.check(str(stored.id))
    if not result.allowed:
        raise APIError(
            429,
            "rate_limited",
            "Too many requests. Try again after the indicated delay.",
            headers={"Retry-After": str(result.retry_after)},
        )
    return stored


def require_scope(required: Scope) -> Callable[..., Awaitable[ApiKey]]:
    """Build a dependency that requires the given scope (write implies read)."""

    async def dependency(
        key: Annotated[ApiKey, Depends(get_current_api_key)],
    ) -> ApiKey:
        if not has_scope(key.scope, required):
            raise APIError(
                403,
                "forbidden",
                f"API key lacks the required '{required.value}' scope.",
            )
        return key

    return dependency
