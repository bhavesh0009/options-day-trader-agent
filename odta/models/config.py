from pydantic import BaseModel
import yaml


class LLMConfig(BaseModel):
    model: str = "gemini-2.0-flash"


class DatabaseConfig(BaseModel):
    path: str = "/Users/bhaveshghodasara/Development/price-vol-pattern/data/stocks.duckdb"


class BrokerConfig(BaseModel):
    mcp_server_path: str = "./angel-one-mcp-server"


class GuardrailsConfig(BaseModel):
    max_daily_loss: int = 5000
    max_open_positions: int = 2
    square_off_time: str = "15:00"
    pre_market_start: str = "08:45"


class AppConfig(BaseModel):
    llm: LLMConfig = LLMConfig()
    database: DatabaseConfig = DatabaseConfig()
    broker: BrokerConfig = BrokerConfig()
    guardrails: GuardrailsConfig = GuardrailsConfig()
    mode: str = "paper"


def load_config(path: str = "config.yaml") -> AppConfig:
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
        return AppConfig(**data)
    except FileNotFoundError:
        return AppConfig()
