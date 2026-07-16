import pytest

from proseforge.infrastructure.security.login_rate_limiter import LoginRateLimiter


class FakeRedis:
    def __init__(self):
        self.counts = {}
        self.expirations = []

    async def incr(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key, seconds):
        self.expirations.append((key, seconds))


@pytest.mark.asyncio
async def test_login_rate_limiter_blocks_after_window_budget():
    redis = FakeRedis()
    limiter = LoginRateLimiter(redis, max_attempts=2, window_seconds=60)

    assert await limiter.allow("user@example.com") is True
    assert await limiter.allow("user@example.com") is True
    assert await limiter.allow("user@example.com") is False
    assert redis.expirations == [("auth:login:user@example.com", 60)]
