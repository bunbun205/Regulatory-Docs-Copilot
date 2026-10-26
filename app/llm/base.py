from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

Role = Literal["system", "user", "assistant", "tool"]


class LLMError(Exception):
    """A safe, provider-independent language-model failure."""


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    # Opaque provider protocol state (e.g. Gemini thought signatures). Never log it.
    extra_content: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class LLMMessage:
    role: Role
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None
    name: str | None = None
    extra_content: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class LLMResult:
    text: str
    tool_calls: tuple[ToolCall, ...] = ()
    usage: TokenUsage = field(default_factory=TokenUsage)
    latency_ms: float = 0.0
    extra_content: dict[str, Any] = field(default_factory=dict, repr=False)


class LLMClient(Protocol):
    async def chat(
        self,
        messages: Sequence[LLMMessage],
        *,
        tools: Sequence[ToolDefinition] = (),
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> LLMResult:
        """Return one normalized completion."""

    async def close(self) -> None:
        """Release provider resources."""
