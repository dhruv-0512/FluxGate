import yaml
from pathlib import Path
from pydantic import BaseModel
from typing import Literal, Optional


class RuleConfig(BaseModel):
    name: str
    key_pattern: str
    algorithm: Literal["token_bucket", "sliding_window", "sliding_window_counter", "leaky_bucket"]
    capacity: Optional[int] = None
    refill_rate: Optional[float] = None
    limit: Optional[int] = None
    window_seconds: Optional[int] = None
    rate: Optional[float] = None
    burst: Optional[int] = None


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080


class RedisConfig(BaseModel):
    url: str = "redis://localhost:6379"


class PostgresConfig(BaseModel):
    url: str = "postgresql+asyncpg://admin:cabbagesucks@localhost:5433/fluxgate"


class AppConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    redis: RedisConfig = RedisConfig()
    postgres: PostgresConfig = PostgresConfig()
    rules: list[RuleConfig] = []


_config: AppConfig = None


def load_config(path: str = None) -> AppConfig:
    global _config

    if path is None:
        path = Path(__file__).resolve().parent.parent.parent / "config.yaml"

    file = Path(path)

    if not file.exists():
        raise FileNotFoundError(f"Config file not found: {file}")

    raw = yaml.safe_load(file.read_text())
    _config = AppConfig(**raw)

    return _config

def get_config() -> AppConfig:
    global _config
    if _config is None:
        load_config()
    return _config

def test_load_config_defaults():
    config = load_config("config.yaml")
    assert isinstance(config, AppConfig)
    assert config.server.port == 8080
    assert config.redis.url == "redis://localhost:6379"