import time
import fnmatch
import asyncio
import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Literal

from app.limiter.token_bucket import TokenBucketLimiter
from app.limiter.sliding_window import SlidingWindowLimiter
from app.limiter.sliding_window_counter import SlidingWindowCounterLimiter
from app.limiter.leaky_bucket import LeakyBucketLimiter
from app.limiter.base import Decision
from app.redis.client import RedisClient
from app.analytics.postgres import AnalyticsDB
from app.analytics.models import RateLimitEvent
from app.metrics.collector import MetricsCollector
from app.config.config import get_config, RuleConfig

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Request / Response Models ───────────────────────────────────────────────

class CheckRequest(BaseModel):
    key: str
    algorithm: Literal[
        "token_bucket",
        "sliding_window",
        "sliding_window_counter",
        "leaky_bucket"
    ] = "sliding_window"
    n: int = 1


class CheckResponse(BaseModel):
    allowed: bool
    remaining: int
    reset_after_ms: int
    retry_after_ms: int
    key: str
    algorithm: str


class StatusResponse(BaseModel):
    key: str
    algorithm: str
    remaining: int
    reset_after_ms: int


# ─── Helpers ─────────────────────────────────────────────────────────────────

def match_rule(key: str) -> Optional[RuleConfig]:
    config = get_config()
    for rule in config.rules:
        if fnmatch.fnmatch(key, rule.key_pattern):
            return rule
    return None


def build_limiter(algorithm: str, rule: Optional[RuleConfig], redis: RedisClient):
    if algorithm == "token_bucket":
        return TokenBucketLimiter(
            redis=redis,
            capacity=rule.capacity if rule and rule.capacity else 100,
            refill_rate=rule.refill_rate if rule and rule.refill_rate else 10.0,
        )
    elif algorithm == "sliding_window":
        return SlidingWindowLimiter(
            redis=redis,
            limit=rule.limit if rule and rule.limit else 100,
            window_seconds=rule.window_seconds if rule and rule.window_seconds else 60,
        )
    elif algorithm == "sliding_window_counter":
        return SlidingWindowCounterLimiter(
            redis=redis,
            limit=rule.limit if rule and rule.limit else 100,
            window_seconds=rule.window_seconds if rule and rule.window_seconds else 60,
        )
    elif algorithm == "leaky_bucket":
        return LeakyBucketLimiter(
            redis=redis,
            rate=rule.rate if rule and rule.rate else 10.0,
            burst=rule.burst if rule and rule.burst else 100,
        )
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.post("/v1/check", response_model=CheckResponse)
async def check_limit(body: CheckRequest, request: Request):
    redis = request.app.state.redis
    db: AnalyticsDB = request.app.state.db
    metrics: MetricsCollector = request.app.state.metrics

    rule = match_rule(body.key)
    algorithm = rule.algorithm if rule else body.algorithm
    limiter = build_limiter(algorithm, rule, redis)
    decision: Decision = await limiter.allow_n(body.key, body.n)

    asyncio.create_task(metrics.record(body.key, decision.allowed))
    asyncio.create_task(db.log_event(RateLimitEvent(
        key=decision.key,
        algorithm=decision.algorithm,
        allowed=decision.allowed,
        remaining=decision.remaining,
        retry_after_ms=decision.retry_after_ms,
    )))

    return CheckResponse(
        allowed=decision.allowed,
        remaining=decision.remaining,
        reset_after_ms=decision.reset_after_ms,
        retry_after_ms=decision.retry_after_ms,
        key=decision.key,
        algorithm=decision.algorithm,
    )


@router.get("/v1/status/{key}", response_model=StatusResponse)
async def get_status(key: str, request: Request):
    redis = request.app.state.redis
    rule = match_rule(key)
    algorithm = rule.algorithm if rule else "sliding_window"
    limiter = build_limiter(algorithm, rule, redis)
    decision = await limiter.status(key)

    return StatusResponse(
        key=decision.key,
        algorithm=decision.algorithm,
        remaining=decision.remaining,
        reset_after_ms=decision.reset_after_ms,
    )


@router.post("/v1/reset/{key}")
async def reset_key(key: str, request: Request):
    redis = request.app.state.redis
    metrics: MetricsCollector = request.app.state.metrics
    rule = match_rule(key)
    algorithm = rule.algorithm if rule else "sliding_window"
    limiter = build_limiter(algorithm, rule, redis)

    deleted = await limiter.reset(key)
    await metrics.reset_key(key)

    return {"key": key, "reset": deleted}


@router.get("/v1/metrics")
async def get_metrics_snapshot(request: Request):
    metrics: MetricsCollector = request.app.state.metrics
    db: AnalyticsDB = request.app.state.db

    snapshot = await metrics.get_snapshot()
    global_stats = await db.get_global_stats()

    return {**snapshot, "db_stats": global_stats}


@router.get("/v1/metrics/{key}")
async def get_key_metrics(key: str, request: Request, minutes: int = 60):
    db: AnalyticsDB = request.app.state.db
    stats = await db.get_stats(key, minutes)

    return {
        "key": key,
        "history": [
            {
                "minute": s.minute.isoformat(),
                "allowed": s.allowed_count,
                "rejected": s.rejected_count,
                "total": s.total,
                "rejection_rate": s.rejection_rate,
            }
            for s in stats
        ]
    }


@router.post("/v1/config/reload")
async def reload_config(request: Request):
    from app.config.config import load_config
    try:
        config = load_config()
        return {"reloaded": True, "rules_count": len(config.rules)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v1/rules")
async def get_rules(request: Request):
    config = get_config()
    return {"rules": [r.model_dump() for r in config.rules]}


@router.get("/health")
async def health(request: Request):
    redis = request.app.state.redis
    redis_ok = await redis.ping()
    return {
        "status": "ok" if redis_ok else "degraded",
        "redis": redis_ok,
        "timestamp": time.time()
    }