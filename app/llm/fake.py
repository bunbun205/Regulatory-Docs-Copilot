from collections.abc import Sequence
from dataclasses import dataclass, field

from app.llm.base import (
    LLMMessage,
    LLMResult,
    TokenUsage,
    ToolCall,
    ToolDefinition,
)


@dataclass(frozen=True)
class FakeResponse:
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    usage: TokenUsage = field(default_factory=TokenUsage)


class FakeLLM:
    """Deterministic scripted client for tests and local smoke runs."""

    def __init__(
        self,
        responses: Sequence[FakeResponse] = (),
        *,
        default_text: str = "Fake answer.",
    ) -> None:
        self._responses = list(responses)
        self._default_text = default_text
        self.requests: list[dict[str, object]] = []

    async def chat(
        self,
        messages: Sequence[LLMMessage],
        *,
        tools: Sequence[ToolDefinition] = (),
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> LLMResult:
        self.requests.append(
            {
                "messages": list(messages),
                "tools": list(tools),
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if self._responses:
            response = self._responses.pop(0)
        else:
            response = FakeResponse(text=self._default_text)
        return LLMResult(
            text=response.text,
            tool_calls=response.tool_calls,
            usage=response.usage,
            latency_ms=0.0,
        )

    async def close(self) -> None:
        return None
