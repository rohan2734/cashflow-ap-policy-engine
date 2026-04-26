import os
from functools import lru_cache
from config.types import AppConfig
from llm.client import LLMClient
from db.connector import DBConnector

# Set during lifespan startup via set_config(); read by every request via get_config().
_config: AppConfig | None = None


def set_config(config: AppConfig) -> None:
    global _config
    _config = config


def get_config() -> AppConfig:
    if _config is None:
        raise RuntimeError("App config not initialized — lifespan did not complete")
    return _config


@lru_cache
def get_db() -> DBConnector:
    return DBConnector(os.environ["DATABASE_URL"])


@lru_cache
def get_llm() -> LLMClient:
    cfg = get_config()
    return LLMClient(
        config=cfg.llm,
        nvidia_api_key=os.environ.get("NVIDIA_API_KEY", ""),
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        aws_credentials={
            "aws_access_key_id": os.environ.get("AWS_ACCESS_KEY_ID", ""),
            "aws_secret_access_key": os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
            "region_name": os.environ.get("AWS_REGION", "us-east-1"),
        },
    )
