from sqlalchemy.ext.asyncio import AsyncSession
from config.types import AppConfig, LLMConfig, ConcurrencyConfig, NotificationConfig
from db import queries

class ConfigError(Exception):
    pass

async def load_config_from_db(session: AsyncSession) -> AppConfig:
    try:
        pipeline = await queries.fetch_active_pipeline(session)
        provider = await queries.fetch_provider(session, pipeline.llm_provider_id)
    except (RuntimeError, KeyError) as exc:
        raise ConfigError(str(exc)) from exc

    pcfg = pipeline.config
    vcfg = provider.config
    try:
        return AppConfig(
            llm=LLMConfig(
                provider=provider.type,
                model=vcfg["model"],
                temperature=vcfg["temperature"],
                max_tokens=vcfg["max_tokens"],
            ),
            concurrency=ConcurrencyConfig(
                max_parallel_clauses=pcfg["concurrency"],
            ),
            notifications=NotificationConfig(
                endpoint=pcfg.get("notification_endpoint", ""),
            ),
            pipeline_id=pipeline.pipeline_id,
            confidence_threshold=pcfg["confidence_threshold"],
        )
    except KeyError as exc:
        raise ConfigError(f"Missing config key in DB: {exc}") from exc