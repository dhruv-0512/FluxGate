import time
from app.limiter.base import RateLimiter, Decision
from app.redis.client import RedisClient


class SlidingWindowCounterLimiter(RateLimiter):
    def __init__(self, redis: RedisClient, limit: int = 100, window_seconds: int = 60):
        self.redis = redis
        self.limit = limit
        self.window_ms = window_seconds * 1000

    def _get_window_keys(self, key: str, now_ms: int):
        curr_window = now_ms // self.window_ms
        prev_window = curr_window - 1
        return f"rl:swc:{key}:{curr_window}", f"rl:swc:{key}:{prev_window}"

    async def allow(self, key: str) -> Decision:
        return await self.allow_n(key, 1)

    async def allow_n(self, key: str, n: int) -> Decision:
        now_ms = int(time.time() * 1000)
        curr_key, prev_key = self._get_window_keys(key, now_ms)
        result = await self.redis.run_script(
            name="sliding_window_counter",
            keys=[curr_key, prev_key],
            args=[self.limit, now_ms, self.window_ms, n]
        )
        allowed = bool(result[0])
        remaining = int(result[1])
        retry_after_ms = int(result[2])
        return Decision(
            allowed=allowed, remaining=remaining,
            reset_after_ms=self.window_ms,
            retry_after_ms=retry_after_ms if not allowed else 0,
            key=key, algorithm="sliding_window_counter"
        )

    async def reset(self, key: str) -> bool:
        now_ms = int(time.time() * 1000)
        curr_key, prev_key = self._get_window_keys(key, now_ms)
        result = await self.redis.client.delete(curr_key, prev_key)
        return result > 0

    async def status(self, key: str) -> Decision:
        return await self.allow_n(key, 0)