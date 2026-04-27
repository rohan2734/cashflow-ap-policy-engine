import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import LLMProviderModel, PromptModel, PipelineModel

_PROVIDER_SPECS = [
    {
        "type": "openrouter",
        "name": "OpenRouter",
        "config": {
            "model": "meta-llama/llama-3-8b-instruct",
            "temperature": 0.1,
            "max_tokens": 2048,
            "base_url": "https://openrouter.ai/api/v1",
        },
    },
    {
        "type": "nvidia",
        "name": "NVIDIA NIM",
        "config": {
            "model": "meta/llama-3-8b-instruct",
            "temperature": 0.1,
            "max_tokens": 2048,
            "base_url": "https://integrate.api.nvidia.com/v1",
        },
    },
    {
        "type": "bedrock",
        "name": "AWS Bedrock",
        "config": {
            "model": "anthropic.claude-3-haiku-20240307-v1:0",
            "temperature": 0.1,
            "max_tokens": 2048,
        },
    },
]

async def seed_defaults(session: AsyncSession) -> None:
    provider = await _seed_llm_providers(session)
    prompt   = await _seed_prompt(session)
    await _seed_pipeline(session, provider.provider_id, prompt.prompt_id)
    await session.commit()

async def _seed_llm_providers(session: AsyncSession) -> LLMProviderModel:
    openrouter: LLMProviderModel | None = None
    for spec in _PROVIDER_SPECS:
        result = await session.execute(
            select(LLMProviderModel).where(LLMProviderModel.type == spec["type"])
        )
        existing = result.scalar_one_or_none()
        if existing:
            if spec["type"] == "openrouter":
                openrouter = existing
        else:
            p = LLMProviderModel(
                provider_id=f"P-{uuid.uuid4().hex[:8].upper()}",
                name=spec["name"],
                type=spec["type"],
                config=spec["config"],
                active=True,
            )
            session.add(p)
            if spec["type"] == "openrouter":
                openrouter = p
    assert openrouter is not None
    return openrouter

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