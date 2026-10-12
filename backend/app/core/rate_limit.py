import asyncio
import time
from collections import defaultdict, deque

from app.core.errors import AppError


class SlidingWindowRateLimiter:
    """A bounded per-process safety limit; production ingress should also rate-limit globally."""

    def __init__(self, requests: int, window_seconds: int, max_keys: int = 10_000) -> None:
        self.requests = requests
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        async with self._lock:
            if len(self._hits) >= self.max_keys and key not in self._hits:
                oldest_key = next(iter(self._hits))
                self._hits.pop(oldest_key, None)
            hits = self._hits[key]
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.requests:
                raise AppError(429, "RATE_LIMITED", "Too many requests. Please try again shortly.")
            hits.append(now)
