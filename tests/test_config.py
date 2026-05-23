import pytest
import tempfile
import os
from app.config.config import load_config, AppConfig


def test_load_config_defaults():
    config = load_config("config.yaml")
    assert isinstance(config, AppConfig)
    assert config.server.port == 8080
    assert config.redis.url == "redis://localhost:6379"


def test_load_config_from_file():
    yaml_content = """
server:
  port: 9090
redis:
  url: "redis://localhost:6380"
rules:
  - name: test_rule
    key_pattern: "test:*"
    algorithm: sliding_window
    limit: 50
    window_seconds: 30
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        tmp_path = f.name

    try:
        config = load_config(tmp_path)
        assert config.server.port == 9090
        assert config.redis.url == "redis://localhost:6380"
        assert len(config.rules) == 1
        assert config.rules[0].name == "test_rule"
        assert config.rules[0].limit == 50
    finally:
        os.unlink(tmp_path)


def test_rule_config_algorithm_validation():
    from app.config.config import RuleConfig
    rule = RuleConfig(
        name="test",
        key_pattern="api:*",
        algorithm="sliding_window",
        limit=100,
        window_seconds=60
    )
    assert rule.algorithm == "sliding_window"