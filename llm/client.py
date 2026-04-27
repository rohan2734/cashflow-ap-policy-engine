import asyncio
import logging
from openai import AsyncOpenAI
from config.types import LLMConfig
from llm.tracing import get_langfuse, get_trace_context

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
        logger.debug(
            "llm_client_init",
            extra={
                "provider": config.provider,
                "model": config.model,
                "temperature": config.temperature,
                "max_tokens": config.max_tokens,
            },
        )
        if config.provider == "nvidia":
            self._openai = AsyncOpenAI(
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=nvidia_api_key,
            )
            logger.info("llm_client_nvidia_initialized", extra={"model": config.model})
        elif config.provider == "openrouter":
            self._openai = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=openrouter_api_key,
            )
            logger.info("llm_client_openrouter_initialized", extra={"model": config.model})
        elif config.provider == "bedrock":
            import boto3
            self._bedrock = boto3.client("bedrock-runtime", **aws_credentials)
            logger.info("llm_client_bedrock_initialized", extra={"model": config.model})

    async def generate(self, prompt: str) -> str:
        langfuse = get_langfuse()
        trace_ctx = get_trace_context()

        generation = langfuse.generation(
            name="llm_generate",
            model=self._config.model,
            model_parameters={
                "temperature": self._config.temperature,
                "max_tokens": self._config.max_tokens,
            },
            input=prompt,
            metadata={
                "provider": self._config.provider,
                **trace_ctx,
            },
        )

        logger.debug(
            "llm_generate_start",
            extra={
                "provider": self._config.provider,
                "model": self._config.model,
                "prompt_length": len(prompt),
                "trace_context": trace_ctx,
            },
        )

        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                result = await self._call(prompt)
                generation.end(output=result)
                logger.info(
                    "llm_generate_success",
                    extra={
                        "provider": self._config.provider,
                        "model": self._config.model,
                        "attempt": attempt + 1,
                        "output_length": len(result),
                    },
                )
                return result
            except Exception as exc:
                last_exc = exc
                wait = 2 ** attempt
                logger.warning(
                    "llm_retry",
                    extra={
                        "attempt": attempt + 1,
                        "wait": wait,
                        "error": str(exc),
                        "provider": self._config.provider,
                        "model": self._config.model,
                    },
                )
                await asyncio.sleep(wait)

        generation.end(level="ERROR", error_message=str(last_exc))
        logger.error(
            "llm_generate_failed",
            extra={
                "provider": self._config.provider,
                "model": self._config.model,
                "attempts": 3,
                "error": str(last_exc),
            },
        )
        raise LLMCallError("LLM call failed after 3 attempts") from last_exc

    async def _call(self, prompt: str) -> str:
        logger.debug(
            "llm_call_start",
            extra={
                "provider": self._config.provider,
                "model": self._config.model,
            },
        )
        if self._config.provider in ("nvidia", "openrouter"):
            return await self._openai_call(prompt)
        return await self._bedrock_call(prompt)

    async def _openai_call(self, prompt: str) -> str:
        logger.debug(
            "llm_openai_call",
            extra={
                "provider": self._config.provider,
                "model": self._config.model,
                "base_url": self._openai.base_url,
            },
        )
        resp = await self._openai.chat.completions.create(
            model=self._config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
        )
        return resp.choices[0].message.content

    async def _bedrock_call(self, prompt: str) -> str:
        logger.debug(
            "llm_bedrock_call",
            extra={
                "provider": self._config.provider,
                "model": self._config.model,
            },
        )
        import json
        body = json.dumps({
            "prompt": prompt,
            "max_tokens_to_sample": self._config.max_tokens,
            "temperature": self._config.temperature,
        })
        resp = self._bedrock.invoke_model(body=body, modelId=self._config.model,
                                          contentType="application/json")
        return json.loads(resp["body"].read())["completion"]