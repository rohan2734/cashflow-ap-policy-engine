import os
from functools import lru_cache
from config.types import AppConfig
from llm.client import LLMClient
from db.connector import DBConnector

_config: AppConfig | None = None
_llm: LLMClient | None = None


def set_config(config: AppConfig) -> None:
    global _config
    _config = config


def get_config() -> AppConfig:
    if _config is None:
        raise RuntimeError("App config not initialized — lifespan did not complete")
    return _config


def build_llm() -> LLMClient:
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


def set_llm(llm: LLMClient) -> None:
    global _llm
    _llm = llm


def get_llm() -> LLMClient:
    if _llm is None:
        raise RuntimeError("LLM client not initialized — lifespan did not complete")
    return _llm


@lru_cache
def get_db() -> DBConnector:
    return DBConnector(os.environ["DATABASE_URL"])
