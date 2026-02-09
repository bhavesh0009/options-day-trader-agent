from pydantic import BaseModel
import yaml

from odta.constants import (
    DEFAULT_MAX_DAILY_LOSS,
    DEFAULT_MAX_OPEN_POSITIONS,
    SQUARE_OFF_TIME_STR,
    PRE_MARKET_START_STR,
)


class LLMConfig(BaseModel):
    model: str  # No default - must be configured in config.yaml


class DatabaseConfig(BaseModel):
    path: str = "/Users/bhaveshghodasara/Development/price-vol-pattern/data/stocks.duckdb"


class BrokerConfig(BaseModel):
    mcp_server_path: str = "./angel-one-mcp-server"


class GuardrailsConfig(BaseModel):
    max_daily_loss: int = DEFAULT_MAX_DAILY_LOSS
    max_open_positions: int = DEFAULT_MAX_OPEN_POSITIONS
    square_off_time: str = SQUARE_OFF_TIME_STR
    pre_market_start: str = PRE_MARKET_START_STR


class AppConfig(BaseModel):
    llm: LLMConfig
    database: DatabaseConfig = DatabaseConfig()
    broker: BrokerConfig = BrokerConfig()
    guardrails: GuardrailsConfig = GuardrailsConfig()
    mode: str = "paper"


def load_config(path: str = "config.yaml") -> AppConfig:
    with open(path) as f:
        data = yaml.safe_load(f)
    return AppConfig(**data)
