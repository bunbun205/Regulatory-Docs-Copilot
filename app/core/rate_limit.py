"""Bounded, process-local token buckets for authenticated identities."""

import math
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after: int = 0


class RateLimiter(Protocol):
    def check(self, identity: str) -> RateLimitResult:
        """Consume one token atomically, or return a positive retry delay."""


@dataclass
class _Bucket:
    tokens: float
    updated_at: float


class TokenBucketRateLimiter:
    """One minute of burst capacity, refilled continuously using monotonic time.

    Only fully replenished inactive buckets may be evicted. When the identity
    bound is reached, new identities wait rather than resetting active limits.
    A shared atomic implementation (e.g. Redis) is needed for multiple workers.
    """

    def __init__(
        self,
        requests_per_minute: int = 60,
        *,
        max_identities: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if requests_per_minute < 1 or max_identities < 1:
            raise ValueError("Rate and identity capacity must be positive.")
        self.capacity = requests_per_minute
        self.max_identities = max_identities
        self._rate = requests_per_minute / 60.0
        self._clock = clock
        self._buckets: OrderedDict[str, _Bucket] = OrderedDict()
        self._lock = threading.Lock()

    def check(self, identity: str) -> RateLimitResult:
        with self._lock:
            now = self._clock()
            while self._buckets:
                oldest = next(iter(self._buckets.values()))
                if now - oldest.updated_at < 60:
                    break
                self._buckets.popitem(last=False)
            bucket = self._buckets.get(identity)
            if bucket is None:
                if len(self._buckets) >= self.max_identities:
                    oldest = next(iter(self._buckets.values()))
                    return RateLimitResult(False, max(1, math.ceil(oldest.updated_at + 60 - now)))
                bucket = _Bucket(float(self.capacity), now)
                self._buckets[identity] = bucket
            bucket.tokens = min(
                self.capacity, bucket.tokens + max(0.0, now - bucket.updated_at) * self._rate
            )
            bucket.updated_at = now
            self._buckets.move_to_end(identity)
            if bucket.tokens < 1 - 1e-12:
                return RateLimitResult(False, max(1, math.ceil((1 - bucket.tokens) / self._rate)))
            bucket.tokens = max(0.0, bucket.tokens - 1)
            return RateLimitResult(True)
