from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import time


@dataclass
class Decision:
    allowed: bool
    remaining: int
    reset_after_ms: int      # ms until window resets
    retry_after_ms: int      # ms until next request allowed (only if rejected)
    key: str
    algorithm: str


class RateLimiter(ABC):

    @abstractmethod
    async def allow(self, key: str) -> Decision:
        """Check if single request is allowed"""
        pass

    @abstractmethod
    async def allow_n(self, key: str, n: int) -> Decision:
        """Check if n requests are allowed"""
        pass

    @abstractmethod
    async def reset(self, key: str) -> bool:
        """Reset a key's state"""
        pass

    @abstractmethod
    async def status(self, key: str) -> Decision:
        """Get current state without consuming"""
        pass