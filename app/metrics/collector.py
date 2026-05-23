import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field


@dataclass
class KeyMetrics:
    allowed: int = 0
    rejected: int = 0
    last_seen: float = field(default_factory=time.time)

    @property
    def total(self) -> int:
        return self.allowed + self.rejected

    @property
    def rejection_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return round(self.rejected / self.total * 100, 2)


class MetricsCollector:
    def __init__(self, window_seconds: int = 60):
        self.window_seconds = window_seconds
        self._key_metrics: dict[str, KeyMetrics] = defaultdict(KeyMetrics)
        self._events: deque = deque()
        self._lock = asyncio.Lock()

    async def record(self, key: str, allowed: bool):
        async with self._lock:
            now = time.time()
            m = self._key_metrics[key]
            if allowed:
                m.allowed += 1
            else:
                m.rejected += 1
            m.last_seen = now
            self._events.append((now, allowed))
            cutoff = now - self.window_seconds
            while self._events and self._events[0][0] < cutoff:
                self._events.popleft()

    async def get_rps(self) -> float:
        async with self._lock:
            now = time.time()
            cutoff = now - 5
            recent = sum(1 for ts, _ in self._events if ts >= cutoff)
            return round(recent / 5, 2)

    async def get_acceptance_rate(self) -> float:
        async with self._lock:
            if not self._events:
                return 100.0
            allowed = sum(1 for _, a in self._events if a)
            return round(allowed / len(self._events) * 100, 2)

    async def get_top_throttled(self, n: int = 10) -> list[dict]:
        async with self._lock:
            sorted_keys = sorted(
                self._key_metrics.items(),
                key=lambda x: x[1].rejected,
                reverse=True
            )
            return [
                {
                    "key": k,
                    "allowed": v.allowed,
                    "rejected": v.rejected,
                    "total": v.total,
                    "rejection_rate": v.rejection_rate,
                    "last_seen": v.last_seen
                }
                for k, v in sorted_keys[:n]
            ]

    async def get_snapshot(self) -> dict:
        rps = await self.get_rps()
        acceptance = await self.get_acceptance_rate()
        top = await self.get_top_throttled()
        async with self._lock:
            total_allowed = sum(m.allowed for m in self._key_metrics.values())
            total_rejected = sum(m.rejected for m in self._key_metrics.values())
        return {
            "rps": rps,
            "acceptance_rate": acceptance,
            "total_allowed": total_allowed,
            "total_rejected": total_rejected,
            "top_throttled": top,
            "timestamp": time.time()
        }

    async def reset_key(self, key: str):
        async with self._lock:
            if key in self._key_metrics:
                del self._key_metrics[key]