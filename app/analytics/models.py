from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class RateLimitEvent:
    key: str
    algorithm: str
    allowed: bool
    remaining: int
    retry_after_ms: int
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class HourlyStats:
    key: str
    minute: datetime
    allowed_count: int
    rejected_count: int
    total: int

    @property
    def rejection_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return round(self.rejected_count / self.total * 100, 2)