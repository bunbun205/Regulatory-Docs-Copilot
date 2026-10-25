import asyncio
import time
from collections.abc import Sequence
from typing import Any

import httpx

from app.llm.base import LLMMessage, LLMResult, ToolDefinition
from app.llm.http import HTTPLLMClient, Sleep
from app.llm.openai_compat import (
    openai_messages,
    openai_tools,
    parse_openai_result,
)


class AzureOpenAIClient(HTTPLLMClient):
    provider = "azure_openai"

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        deployment: str,
        api_version: str = "2024-10-21",
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        super().__init__(
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            transport=transport,
            sleep=sleep,
        )
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.deployment = deployment
        self.api_version = api_version

    async def chat(
        self,
        messages: Sequence[LLMMessage],
        *,
        tools: Sequence[ToolDefinition] = (),
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> LLMResult:
        payload: dict[str, Any] = {
            "messages": openai_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = openai_tools(tools)
            payload["tool_choice"] = "auto"
        started = time.perf_counter()
        body = await self._post_json(
            f"{self.endpoint}/openai/deployments/{self.deployment}/chat/completions"
            f"?api-version={self.api_version}",
            headers={
                "Content-Type": "application/json",
                "api-key": self.api_key,
            },
            payload=payload,
            provider=self.provider,
        )
        return parse_openai_result(body, (time.perf_counter() - started) * 1000)
