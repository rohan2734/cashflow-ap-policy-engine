import asyncio
import logging
from openai import AsyncOpenAI
from config.types import LLMConfig

logger = logging.getLogger(__name__)


class LLMCallError(Exception):
    pass


class LLMClient:
    def __init__(
        self,
        config: LLMConfig,
        nvidia_api_key: str,
        openrouter_api_key: str,
        aws_credentials: dict,
    ) -> None:
        self._config = config
        if config.provider == "nvidia":
            self._openai = AsyncOpenAI(
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=nvidia_api_key,
            )
        elif config.provider == "openrouter":
            self._openai = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=openrouter_api_key,
            )
        elif config.provider == "bedrock":
            import boto3
            self._bedrock = boto3.client("bedrock-runtime", **aws_credentials)

    async def generate(self, prompt: str) -> str:
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                return await self._call(prompt)
            except Exception as exc:
                last_exc = exc
                wait = 2 ** attempt
                logger.warning("llm_retry", extra={"attempt": attempt, "wait": wait, "error": str(exc)})
                await asyncio.sleep(wait)
        raise LLMCallError("LLM call failed after 3 attempts") from last_exc

    async def _call(self, prompt: str) -> str:
        if self._config.provider in ("nvidia", "openrouter"):
            return await self._openai_call(prompt)
        return await self._bedrock_call(prompt)

    async def _openai_call(self, prompt: str) -> str:
        resp = await self._openai.chat.completions.create(
            model=self._config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
        )
        return resp.choices[0].message.content

    async def _bedrock_call(self, prompt: str) -> str:
        import json
        body = json.dumps({
            "prompt": prompt,
            "max_tokens_to_sample": self._config.max_tokens,
            "temperature": self._config.temperature,
        })
        resp = self._bedrock.invoke_model(body=body, modelId=self._config.model,
                                          contentType="application/json")
        return json.loads(resp["body"].read())["completion"]