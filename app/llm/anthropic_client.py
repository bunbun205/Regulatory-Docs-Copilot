import asyncio
import time
from collections.abc import Sequence
from typing import Any

import httpx

from app.llm.base import (
    LLMError,
    LLMMessage,
    LLMResult,
    TokenUsage,
    ToolCall,
    ToolDefinition,
)
from app.llm.http import HTTPLLMClient, Sleep


def anthropic_messages(
    messages: Sequence[LLMMessage],
) -> tuple[str | None, list[dict[str, Any]]]:
    system_parts: list[str] = []
    converted: list[dict[str, Any]] = []
    for message in messages:
        if message.role == "system":
            system_parts.append(message.content)
            continue
        if message.role == "tool":
            block = {
                "type": "tool_result",
                "tool_use_id": message.tool_call_id or "",
                "content": message.content,
            }
            if converted and converted[-1].get("role") == "user":
                previous_content = converted[-1].get("content")
                if isinstance(previous_content, list) and any(
                    isinstance(item, dict) and item.get("type") == "tool_result"
                    for item in previous_content
                ):
                    previous_content.append(block)
                    continue
            converted.append({"role": "user", "content": [block]})
            continue
        if message.role == "assistant" and message.tool_calls:
            content: list[dict[str, Any]] = []
            if message.content:
                content.append({"type": "text", "text": message.content})
            content.extend(
                {
                    "type": "tool_use",
                    "id": call.id,
                    "name": call.name,
                    "input": call.arguments,
                }
                for call in message.tool_calls
            )
            converted.append({"role": "assistant", "content": content})
            continue
        converted.append({"role": message.role, "content": message.content})
    return ("\n\n".join(system_parts) if system_parts else None), converted


def anthropic_tools(tools: Sequence[ToolDefinition]) -> list[dict[str, Any]]:
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.parameters,
        }
        for tool in tools
    ]


def parse_anthropic_result(body: dict[str, Any], latency_ms: float) -> LLMResult:
    try:
        blocks = body["content"]
    except (KeyError, TypeError) as exc:
        raise LLMError("Language model returned an unexpected response.") from exc
    if not isinstance(blocks, list):
        raise LLMError("Language model returned an unexpected response.")
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            text_parts.append(str(block.get("text") or ""))
        elif block.get("type") == "tool_use":
            arguments = block.get("input")
            tool_calls.append(
                ToolCall(
                    id=str(block.get("id") or ""),
                    name=str(block.get("name") or ""),
                    arguments=arguments if isinstance(arguments, dict) else {},
                )
            )
    usage = body.get("usage") or {}
    return LLMResult(
        text="".join(text_parts),
        tool_calls=tuple(tool_calls),
        usage=TokenUsage(
            input_tokens=int(usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or 0),
        ),
        latency_ms=latency_ms,
    )


class AnthropicClient(HTTPLLMClient):
    provider = "anthropic"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.anthropic.com",
        version: str = "2023-06-01",
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
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.version = version

    async def chat(
        self,
        messages: Sequence[LLMMessage],
        *,
        tools: Sequence[ToolDefinition] = (),
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> LLMResult:
        system, converted = anthropic_messages(messages)
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": converted,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = anthropic_tools(tools)
        started = time.perf_counter()
        body = await self._post_json(
            f"{self.base_url}/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": self.version,
            },
            payload=payload,
            provider=self.provider,
        )
        return parse_anthropic_result(body, (time.perf_counter() - started) * 1000)
