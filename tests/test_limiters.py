import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from app.limiter.token_bucket import TokenBucketLimiter
from app.limiter.sliding_window import SlidingWindowLimiter
from app.limiter.sliding_window_counter import SlidingWindowCounterLimiter
from app.limiter.leaky_bucket import LeakyBucketLimiter


def make_redis(return_value):
    redis = MagicMock()
    redis.run_script = AsyncMock(return_value=return_value)
    redis.client = MagicMock()
    redis.client.delete = AsyncMock(return_value=1)
    return redis


# ─── Token Bucket ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_token_bucket_allowed():
    redis = make_redis([1, 99, 0])
    limiter = TokenBucketLimiter(redis=redis, capacity=100, refill_rate=10.0)
    decision = await limiter.allow("user:1")
    assert decision.allowed is True
    assert decision.remaining == 99
    assert decision.algorithm == "token_bucket"


@pytest.mark.asyncio
async def test_token_bucket_rejected():
    redis = make_redis([0, 0, 5000])
    limiter = TokenBucketLimiter(redis=redis, capacity=100, refill_rate=10.0)
    decision = await limiter.allow("user:1")
    assert decision.allowed is False
    assert decision.retry_after_ms == 5000


@pytest.mark.asyncio
async def test_token_bucket_reset():
    redis = make_redis([1, 99, 0])
    limiter = TokenBucketLimiter(redis=redis, capacity=100, refill_rate=10.0)
    result = await limiter.reset("user:1")
    assert result is True


# ─── Sliding Window ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_sliding_window_allowed():
    redis = make_redis([1, 49, 0])
    limiter = SlidingWindowLimiter(redis=redis, limit=100, window_seconds=60)
    decision = await limiter.allow("user:2")
    assert decision.allowed is True
    assert decision.remaining == 49
    assert decision.algorithm == "sliding_window"


@pytest.mark.asyncio
async def test_sliding_window_rejected():
    redis = make_redis([0, 0, 3000])
    limiter = SlidingWindowLimiter(redis=redis, limit=100, window_seconds=60)
    decision = await limiter.allow("user:2")
    assert decision.allowed is False
    assert decision.retry_after_ms == 3000


# ─── Sliding Window Counter ──────────────────────────────────

@pytest.mark.asyncio
async def test_sliding_window_counter_allowed():
    redis = make_redis([1, 79, 0])
    limiter = SlidingWindowCounterLimiter(redis=redis, limit=100, window_seconds=60)
    decision = await limiter.allow("user:3")
    assert decision.allowed is True
    assert decision.algorithm == "sliding_window_counter"


@pytest.mark.asyncio
async def test_sliding_window_counter_rejected():
    redis = make_redis([0, 0, 10000])
    limiter = SlidingWindowCounterLimiter(redis=redis, limit=100, window_seconds=60)
    decision = await limiter.allow("user:3")
    assert decision.allowed is False


# ─── Leaky Bucket ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_leaky_bucket_allowed():
    redis = make_redis([1, 9, 0])
    limiter = LeakyBucketLimiter(redis=redis, rate=10.0, burst=100)
    decision = await limiter.allow("user:4")
    assert decision.allowed is True
    assert decision.algorithm == "leaky_bucket"


@pytest.mark.asyncio
async def test_leaky_bucket_rejected():
    redis = make_redis([0, 0, 2000])
    limiter = LeakyBucketLimiter(redis=redis, rate=10.0, burst=100)
    decision = await limiter.allow("user:4")
    assert decision.allowed is False
    assert decision.retry_after_ms == 2000


# ─── allow_n ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_allow_n_consumes_n_tokens():
    redis = make_redis([1, 95, 0])
    limiter = TokenBucketLimiter(redis=redis, capacity=100, refill_rate=10.0)
    decision = await limiter.allow_n("user:5", 5)
    call_args = redis.run_script.call_args
    assert call_args.kwargs["args"][-1] == 5


@pytest.mark.asyncio
async def test_status_does_not_consume():
    redis = make_redis([1, 100, 0])
    limiter = SlidingWindowLimiter(redis=redis, limit=100, window_seconds=60)
    decision = await limiter.status("user:6")
    call_args = redis.run_script.call_args
    assert call_args.kwargs["args"][-1] == 0