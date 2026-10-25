import json

import httpx
import pytest

from app.core.config import Settings
from app.llm.anthropic_client import AnthropicClient
from app.llm.azure_openai_client import AzureOpenAIClient
from app.llm.base import LLMError, LLMMessage, ToolCall, ToolDefinition
from app.llm.factory import build_llm_client
from app.llm.openai_compat import OpenAICompatibleClient

TOOL = ToolDefinition(
    name="search_documents",
    description="Search the corpus.",
    parameters={"type": "object", "properties": {"query": {"type": "string"}}},
)


def _openai_body() -> dict[str, object]:
    return {
        "choices": [
            {
                "message": {
                    "content": "Here is an answer.",
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "type": "function",
                            "function": {
                                "name": "search_documents",
                                "arguments": json.dumps({"query": "records"}),
                            },
                        }
                    ],
                }
            }
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 7},
    }


async def test_openai_compatible_client_sends_tools_and_parses_result() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_openai_body())

    client = OpenAICompatibleClient(
        base_url="http://llm.local/v1",
        model="test-model",
        api_key="secret",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await client.chat(
            [LLMMessage(role="user", content="Find records")],
            tools=[TOOL],
            temperature=0.2,
            max_tokens=100,
        )
    finally:
        await client.close()

    assert seen["url"] == "http://llm.local/v1/chat/completions"
    assert seen["authorization"] == "Bearer secret"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["model"] == "test-model"
    assert body["temperature"] == 0.2
    assert body["tools"][0]["function"]["name"] == "search_documents"
    assert result.text == "Here is an answer."
    assert result.tool_calls == (
        ToolCall(id="call-1", name="search_documents", arguments={"query": "records"}),
    )
    assert result.usage.input_tokens == 12
    assert result.usage.output_tokens == 7


async def test_anthropic_client_parses_text_and_tool_use() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["api_key"] = request.headers.get("x-api-key")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "content": [
                    {"type": "text", "text": "Anthropic answer."},
                    {
                        "type": "tool_use",
                        "id": "tool-1",
                        "name": "search_documents",
                        "input": {"query": "labels"},
                    },
                ],
                "usage": {"input_tokens": 20, "output_tokens": 9},
            },
        )

    client = AnthropicClient(
        api_key="anthropic-secret",
        model="claude-test",
        base_url="http://anthropic.local",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await client.chat(
            [
                LLMMessage(role="system", content="Be precise."),
                LLMMessage(role="user", content="Find labels"),
            ],
            tools=[TOOL],
        )
    finally:
        await client.close()

    assert seen["url"] == "http://anthropic.local/v1/messages"
    assert seen["api_key"] == "anthropic-secret"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["system"] == "Be precise."
    assert body["tools"][0]["input_schema"]["type"] == "object"
    assert result.text == "Anthropic answer."
    assert result.tool_calls[0].arguments == {"query": "labels"}
    assert result.usage.input_tokens == 20


async def test_azure_openai_client_uses_deployment_url() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["api_key"] = request.headers.get("api-key")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_openai_body())

    client = AzureOpenAIClient(
        endpoint="https://example.openai.azure.com",
        api_key="azure-secret",
        deployment="chat-deployment",
        api_version="2024-10-21",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await client.chat([LLMMessage(role="user", content="Find records")])
    finally:
        await client.close()

    assert "deployments/chat-deployment/chat/completions" in str(seen["url"])
    assert "api-version=2024-10-21" in str(seen["url"])
    assert seen["api_key"] == "azure-secret"
    assert result.text == "Here is an answer."


async def test_retryable_status_is_retried_with_bounded_delay() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, json=_openai_body())

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    client = OpenAICompatibleClient(
        base_url="http://llm.local/v1",
        model="test-model",
        max_retries=1,
        transport=httpx.MockTransport(handler),
        sleep=fake_sleep,
    )
    try:
        result = await client.chat([LLMMessage(role="user", content="hello")])
    finally:
        await client.close()

    assert attempts == 2
    assert len(delays) == 1
    assert result.text == "Here is an answer."


async def test_non_retryable_error_raises_safe_llm_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "secret provider detail"})

    client = OpenAICompatibleClient(
        base_url="http://llm.local/v1",
        model="test-model",
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(LLMError) as exc_info:
            await client.chat([LLMMessage(role="user", content="hello")])
    finally:
        await client.close()

    assert "secret provider detail" not in str(exc_info.value)


def test_fake_provider_is_refused_in_production() -> None:
    production = Settings(LLM_PROVIDER="fake", ENVIRONMENT="production")
    with pytest.raises(RuntimeError, match="not allowed in production"):
        build_llm_client(production)


def test_fake_provider_is_available_outside_production() -> None:
    development = Settings(LLM_PROVIDER="fake", ENVIRONMENT="development")
    client = build_llm_client(development)
    assert client.__class__.__name__ == "FakeLLM"
