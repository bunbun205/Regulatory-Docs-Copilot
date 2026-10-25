import asyncio
import json
import random
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import httpx
import structlog

from app.llm.base import LLMError

logger = structlog.get_logger("labdocs.llm")

Sleep = Callable[[float], Awaitable[None]]


class HTTPLLMClient:
    """Shared HTTP transport, timeout and bounded-retry behavior."""

    def __init__(
        self,
        *,
        timeout_seconds: float,
        max_retries: int,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
        )
        self._max_retries = max_retries
        self._sleep = sleep

    async def close(self) -> None:
        await self._client.aclose()

    async def _post_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: dict[str, Any],
        provider: str,
    ) -> dict[str, Any]:
        last_reason = "request failed"
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.post(url, headers=headers, json=payload)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_reason = type(exc).__name__
            else:
                if response.status_code < 400:
                    try:
                        body = response.json()
                    except ValueError as exc:
                        raise LLMError("Language model returned invalid JSON.") from exc
                    if not isinstance(body, dict):
                        raise LLMError("Language model returned an unexpected response.")
                    return body
                last_reason = f"HTTP {response.status_code}"
                if response.status_code != 429 and response.status_code < 500:
                    logger.error(
                        "llm.request_rejected",
                        provider=provider,
                        status_code=response.status_code,
                    )
                    raise LLMError(f"Language model request was rejected ({last_reason}).")

            if attempt < self._max_retries:
                delay = min(8.0, 0.25 * (2**attempt)) + random.uniform(0, 0.1)
                logger.warning(
                    "llm.request_retry",
                    provider=provider,
                    attempt=attempt + 1,
                    reason=last_reason,
                )
                await self._sleep(delay)

        logger.error("llm.request_failed", provider=provider, reason=last_reason)
        raise LLMError("Language model is temporarily unavailable.")


def parse_tool_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
