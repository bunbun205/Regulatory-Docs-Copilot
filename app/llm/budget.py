"""Reserve a conservative token allowance before every provider attempt.

UTF-8 request bytes plus framing allowance bound ordinary byte/subword input
tokenizers; output uses the requested maximum. This is an admission budget,
not a provider billing guarantee (remote tokenizers/hidden reasoning may differ).
Unknown usage retains the whole reservation, and reported overruns fail closed.
"""

import json
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from app.llm.base import LLMError, TokenUsage


class TokenBudgetExceeded(LLMError):
    pass


@dataclass
class TokenBudget:
    limit: int
    charged_tokens: int = 0
    unreported_tokens: int = 0
    attempts: int = 0
    cap_hit: bool = False
    provider_overrun: bool = False
    usage: TokenUsage = TokenUsage()

    def reserve(self, payload: object, max_tokens: int) -> int:
        amount = len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) + 1024 + max_tokens
        # No await between checking and reserving: concurrent asyncio calls share
        # the same allowance without a check-then-call race.
        if self.provider_overrun or self.charged_tokens + amount > self.limit:
            self.cap_hit = True
            raise TokenBudgetExceeded("Per-run token allowance exhausted.")
        self.charged_tokens += amount
        self.unreported_tokens += amount
        self.attempts += 1
        return amount

    def settle(self, reservation: int, usage: TokenUsage | None) -> None:
        if usage is None or usage.total_tokens <= 0:
            return
        if usage.input_tokens < 0 or usage.output_tokens < 0:
            return
        self.unreported_tokens -= reservation
        self.charged_tokens += usage.total_tokens - reservation
        self.usage = TokenUsage(
            self.usage.input_tokens + usage.input_tokens,
            self.usage.output_tokens + usage.output_tokens,
        )
        if usage.total_tokens > reservation:
            # Retain the true usage rather than clamping the report to the cap.
            self.cap_hit = True
            self.provider_overrun = True
            raise TokenBudgetExceeded("Provider usage exceeded the reserved allowance.")

    def summary(self) -> dict[str, int | str | bool]:
        return {
            "accounting": "utf8_reservation",
            "charged_tokens": self.charged_tokens,
            "unreported_tokens_reserved": self.unreported_tokens,
            "provider_attempts": self.attempts,
            "cap_hit": self.cap_hit,
            "provider_overrun": self.provider_overrun,
        }


active_token_budget: ContextVar[TokenBudget | None] = ContextVar("token_budget", default=None)


def response_usage(body: Mapping[str, Any]) -> TokenUsage | None:
    usage = body.get("usage")
    if not isinstance(usage, dict):
        return None
    try:
        return TokenUsage(
            input_tokens=int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
            + int(usage.get("cache_creation_input_tokens", 0))
            + int(usage.get("cache_read_input_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
        )
    except (TypeError, ValueError, OverflowError):
        return None
