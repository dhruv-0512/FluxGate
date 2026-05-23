import time
from app.limiter.base import RateLimiter, Decision
from app.redis.client import RedisClient


class TokenBucketLimiter(RateLimiter):
    def __init__(self, redis: RedisClient, capacity: int = 100, refill_rate: float = 10.0):
        self.redis = redis
        self.capacity = capacity
        self.refill_rate = refill_rate

    async def allow(self, key: str) -> Decision:
        return await self.allow_n(key, 1)

    async def allow_n(self, key: str, n: int) -> Decision:
        now_ms = int(time.time() * 1000)
        result = await self.redis.run_script(
            name="token_bucket",
            keys=[f"rl:tb:{key}"],
            args=[self.capacity, self.refill_rate, now_ms, n]
        )
        allowed = bool(result[0])
        remaining = int(result[1])
        retry_after_ms = int(result[2])
        reset_after_ms = int(((self.capacity - remaining) / self.refill_rate) * 1000)
        return Decision(
            allowed=allowed,
            remaining=remaining,
            reset_after_ms=reset_after_ms,
            retry_after_ms=retry_after_ms if not allowed else 0,
            key=key,
            algorithm="token_bucket"
        )

    async def reset(self, key: str) -> bool:
        result = await self.redis.client.delete(f"rl:tb:{key}")
        return result > 0

    async def status(self, key: str) -> Decision:
        return await self.allow_n(key, 0)
    