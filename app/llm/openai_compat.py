import asyncio
import json
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
from app.llm.http import HTTPLLMClient, Sleep, parse_tool_arguments


def openai_messages(messages: Sequence[LLMMessage]) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for message in messages:
        if message.role == "assistant" and message.tool_calls:
            converted.append(
                {
                    "role": "assistant",
                    "content": message.content or None,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": json.dumps(call.arguments),
                            },
                            **({"extra_content": call.extra_content} if call.extra_content else {}),
                        }
                        for call in message.tool_calls
                    ],
                }
            )
        elif message.role == "tool":
            converted.append(
                {
                    "role": "tool",
                    "tool_call_id": message.tool_call_id or "",
                    "content": message.content,
                }
            )
        else:
            converted.append({"role": message.role, "content": message.content})
        if message.role == "assistant" and message.extra_content:
            converted[-1]["extra_content"] = message.extra_content
    return converted


def openai_tools(tools: Sequence[ToolDefinition]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in tools
    ]


def parse_openai_result(body: dict[str, Any], latency_ms: float) -> LLMResult:
    try:
        choice = body["choices"][0]
        message = choice["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("Language model returned an unexpected response.") from exc
    tool_calls: list[ToolCall] = []
    for raw_call in message.get("tool_calls") or []:
        function = raw_call.get("function") or {}
        tool_calls.append(
            ToolCall(
                id=str(raw_call.get("id") or ""),
                name=str(function.get("name") or ""),
                arguments=parse_tool_arguments(function.get("arguments")),
                extra_content=_extra_content(raw_call),
            )
        )
    usage = body.get("usage") or {}
    return LLMResult(
        text=str(message.get("content") or ""),
        tool_calls=tuple(tool_calls),
        usage=TokenUsage(
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
        ),
        latency_ms=latency_ms,
        extra_content=_extra_content(message),
    )


def _extra_content(message: dict[str, Any]) -> dict[str, Any]:
    content = message.get("extra_content")
    if content is None:
        return {}
    if not isinstance(content, dict):
        raise LLMError("Language model returned invalid protocol metadata.")
    return content


class OpenAICompatibleClient(HTTPLLMClient):
    """OpenAI-compatible chat completions (including Groq, Gemini and Ollama)."""

    provider = "openai_compatible"

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        reasoning_effort: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        super().__init__(
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            transport=transport,
            sleep=sleep,
        )
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.reasoning_effort = reasoning_effort

    async def chat(
        self,
        messages: Sequence[LLMMessage],
        *,
        tools: Sequence[ToolDefinition] = (),
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> LLMResult:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": openai_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = openai_tools(tools)
            payload["tool_choice"] = "auto"
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort
        started = time.perf_counter()
        body = await self._post_json(
            f"{self.base_url}/chat/completions",
            headers=headers,
            payload=payload,
            provider=self.provider,
        )
        return parse_openai_result(body, (time.perf_counter() - started) * 1000)
