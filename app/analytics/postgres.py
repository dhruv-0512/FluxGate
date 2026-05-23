import asyncpg
import logging
from app.analytics.models import RateLimitEvent, HourlyStats

logger = logging.getLogger(__name__)


class AnalyticsDB:
    def __init__(self, url: str):
        self.url = url.replace("postgresql+asyncpg://", "postgresql://")
        self.pool: asyncpg.Pool = None

    async def connect(self):
        print("DB URL =", self.url)
        self.pool = await asyncpg.create_pool(self.url, min_size=2, max_size=10)
        await self._run_migrations()
        logger.info("Postgres connected")

    async def disconnect(self):
        if self.pool:
            await self.pool.close()

    async def _run_migrations(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS rate_limit_events (
                    id BIGSERIAL PRIMARY KEY,
                    key TEXT NOT NULL,
                    algorithm TEXT NOT NULL,
                    allowed BOOLEAN NOT NULL,
                    remaining INTEGER,
                    retry_after_ms INTEGER,
                    timestamp TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_key_timestamp ON rate_limit_events(key, timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_timestamp ON rate_limit_events(timestamp DESC);
            """)
        logger.info("Migrations done")

    async def log_event(self, event: RateLimitEvent):
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO rate_limit_events
                        (key, algorithm, allowed, remaining, retry_after_ms, timestamp)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, event.key, event.algorithm, event.allowed,
                    event.remaining, event.retry_after_ms, event.timestamp)
        except Exception as e:
            logger.error(f"Failed to log event: {e}")

    async def get_stats(self, key: str, minutes: int = 60) -> list[HourlyStats]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    key,
                    date_trunc('minute', timestamp) as minute,
                    COUNT(*) FILTER (WHERE allowed) as allowed_count,
                    COUNT(*) FILTER (WHERE NOT allowed) as rejected_count,
                    COUNT(*) as total
                FROM rate_limit_events
                WHERE key = $1
                  AND timestamp > NOW() - ($2 || ' minutes')::interval
                GROUP BY key, date_trunc('minute', timestamp)
                ORDER BY minute DESC
            """, key, str(minutes))
        return [
            HourlyStats(
                key=row["key"],
                minute=row["minute"],
                allowed_count=row["allowed_count"],
                rejected_count=row["rejected_count"],
                total=row["total"]
            )
            for row in rows
        ]

    async def get_top_throttled(self, limit: int = 10) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    key,
                    COUNT(*) FILTER (WHERE NOT allowed) as rejected_count,
                    COUNT(*) as total,
                    ROUND(
                        COUNT(*) FILTER (WHERE NOT allowed)::numeric
                        / NULLIF(COUNT(*), 0) * 100, 2
                    ) as rejection_rate
                FROM rate_limit_events
                WHERE timestamp > NOW() - INTERVAL '1 hour'
                GROUP BY key
                ORDER BY rejected_count DESC
                LIMIT $1
            """, limit)
        return [dict(row) for row in rows]

    async def get_global_stats(self) -> dict:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE allowed) as allowed,
                    COUNT(*) FILTER (WHERE NOT allowed) as rejected
                FROM rate_limit_events
                WHERE timestamp > NOW() - INTERVAL '1 minute'
            """)
        return {
            "total_per_min": row["total"],
            "allowed_per_min": row["allowed"],
            "rejected_per_min": row["rejected"],
            "rejection_rate": round(row["rejected"] / max(row["total"], 1) * 100, 2)
        }