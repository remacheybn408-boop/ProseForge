from __future__ import annotations

from typing import Protocol

from redis.asyncio import Redis


class _Counter(Protocol):
    async def incr(self, key: str) -> int: ...
    async def expire(self, key: str, seconds: int) -> object: ...


class LoginRateLimiter:
    def __init__(self, redis: _Counter, *, max_attempts: int = 5, window_seconds: int = 60):
        self.redis = redis
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds

    @classmethod
    def from_url(cls, url: str, *, max_attempts: int = 5, window_seconds: int = 60) -> "LoginRateLimiter":
        return cls(Redis.from_url(url), max_attempts=max_attempts, window_seconds=window_seconds)

    async def allow(self, identity: str) -> bool:
        key = f"auth:login:{identity}"
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, self.window_seconds)
        return count <= self.max_attempts
