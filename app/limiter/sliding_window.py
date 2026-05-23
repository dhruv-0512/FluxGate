import time
from app.limiter.base import RateLimiter, Decision
from app.redis.client import RedisClient


class SlidingWindowLimiter(RateLimiter):
    def __init__(self, redis: RedisClient, limit: int = 100, window_seconds: int = 60):
        self.redis = redis
        self.limit = limit
        self.window_ms = window_seconds * 1000

    async def allow(self, key: str) -> Decision:
        return await self.allow_n(key, 1)

    async def allow_n(self, key: str, n: int) -> Decision:
        now_ms = int(time.time() * 1000)
        result = await self.redis.run_script(
            name="sliding_window",
            keys=[f"rl:sw:{key}"],
            args=[self.window_ms, self.limit, now_ms, n]
        )
        allowed = bool(result[0])
        remaining = int(result[1])
        retry_after_ms = int(result[2])
        return Decision(
            allowed=allowed, remaining=remaining,
            reset_after_ms=self.window_ms,
            retry_after_ms=retry_after_ms if not allowed else 0,
            key=key, algorithm="sliding_window"
        )

    async def reset(self, key: str) -> bool:
        result = await self.redis.client.delete(f"rl:sw:{key}")
        return result > 0

    async def status(self, key: str) -> Decision:
        return await self.allow_n(key, 0)