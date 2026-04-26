import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import LLMProviderModel, PromptModel, PipelineModel

async def seed_defaults(session: AsyncSession) -> None:
    provider = await _seed_llm_provider(session)
    prompt   = await _seed_prompt(session)
    await _seed_pipeline(session, provider.provider_id, prompt.prompt_id)
    await session.commit()

async def _seed_llm_provider(session: AsyncSession) -> LLMProviderModel:
    result = await session.execute(select(LLMProviderModel).limit(1))
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    provider = LLMProviderModel(
        provider_id=f"P-{uuid.uuid4().hex[:8].upper()}",
        name="OpenRouter Default",
        type="openrouter",
        config={
            # extraction default — fast, stable JSON output
            "model": "meta-llama/llama-3-8b-instruct",
            "temperature": 0.1,
            "max_tokens": 2048,
            "base_url": "https://openrouter.ai/api/v1",
        },
        active=True,
    )
    session.add(provider)
    return provider

async def _seed_prompt(session: AsyncSession) -> PromptModel:
    result = await session.execute(select(PromptModel).limit(1))
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    prompt = PromptModel(
        prompt_id=f"PR-{uuid.uuid4().hex[:8].upper()}",
        name="extraction",
        version=1,
        langfuse_prompt_id=None,   # wired after Langfuse is set up in Phase 9
        active=True,
    )
    session.add(prompt)
    return prompt

async def _seed_pipeline(
    session: AsyncSession,
    llm_provider_id: str,
    prompt_id: str,
) -> None:
    result = await session.execute(select(PipelineModel).limit(1))
    if result.scalar_one_or_none():
        return
    session.add(PipelineModel(
        pipeline_id=f"PL-{uuid.uuid4().hex[:8].upper()}",
        name="Default Extraction Pipeline",
        llm_provider_id=llm_provider_id,
        prompt_id=prompt_id,
        config={
            "confidence_threshold": 0.5,
            "concurrency": 5,
            "notification_endpoint": "",
        },
        active=True,
    ))