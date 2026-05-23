import time
from app.limiter.base import RateLimiter, Decision
from app.redis.client import RedisClient


class LeakyBucketLimiter(RateLimiter):
    def __init__(self, redis: RedisClient, rate: float = 10.0, burst: int = 100):
        self.redis = redis
        self.rate = rate
        self.burst = burst

    async def allow(self, key: str) -> Decision:
        return await self.allow_n(key, 1)

    async def allow_n(self, key: str, n: int) -> Decision:
        now_ms = int(time.time() * 1000)
        result = await self.redis.run_script(
            name="leaky_bucket",
            keys=[f"rl:lb:{key}"],
            args=[self.rate, self.burst, now_ms, n]
        )
        allowed = bool(result[0])
        remaining = int(result[1])
        retry_after_ms = int(result[2])
        reset_after_ms = int((self.burst / self.rate) * 1000)
        return Decision(
            allowed=allowed, remaining=remaining,
            reset_after_ms=reset_after_ms,
            retry_after_ms=retry_after_ms if not allowed else 0,
            key=key, algorithm="leaky_bucket"
        )

    async def reset(self, key: str) -> bool:
        result = await self.redis.client.delete(f"rl:lb:{key}")
        return result > 0

    async def status(self, key: str) -> Decision:
        return await self.allow_n(key, 0)