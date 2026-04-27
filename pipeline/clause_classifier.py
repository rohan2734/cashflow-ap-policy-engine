import json
import logging
import re

from shared_types.pipeline import RawBlock
from llm.client import LLMClient
from llm.prompts import CLASSIFY_PROMPT

logger = logging.getLogger(__name__)

_NUMBERED = re.compile(r"^(\d+(\.\d+)*(\([a-z]\))?)\s")
_BLOCK_PREVIEW_CHARS = 200


class ClassificationError(Exception):
    pass


async def classify_normative_blocks(blocks: list[RawBlock], llm: LLMClient) -> list[RawBlock]:
    logger.debug(
        "classify_start",
        extra={"total_blocks": len(blocks)},
    )

    if not blocks:
        logger.info("classify_empty_blocks")
        return []

    numbered_indices = {i for i, b in enumerate(blocks) if _NUMBERED.match(b.text)}
    logger.debug(
        "classify_numbered_blocks",
        extra={"numbered_count": len(numbered_indices)},
    )

    blocks_text = "\n".join(
        f"{i}: {b.text[:_BLOCK_PREVIEW_CHARS]}" for i, b in enumerate(blocks)
    )
    logger.debug(
        "classify_llm_call_start",
        extra={
            "blocks_count": len(blocks),
            "text_length": len(blocks_text),
        },
    )

    raw = await llm.generate(CLASSIFY_PROMPT.format(blocks=blocks_text))

    logger.info(
        "classify_llm_response_received",
        extra={
            "blocks_count": len(blocks),
            "response_length": len(raw),
            "response_preview": raw[:500] if len(raw) > 500 else raw,
        },
    )

    try:
        # Try to extract JSON from markdown code blocks first
        json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', raw, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Fallback: try to find JSON object in the response
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                # Last resort: try parsing the entire response
                json_str = raw.strip()

        parsed = json.loads(json_str)
        llm_indices = set(parsed["normative_indices"])
        logger.info(
            "classify_parse_success",
            extra={
                "llm_indices": list(llm_indices),
                "llm_indices_count": len(llm_indices),
                "parsed_json_keys": list(parsed.keys()),
            },
        )
    except (json.JSONDecodeError, KeyError) as exc:
        logger.error(
            "classify_parse_error",
            extra={
                "error": str(exc),
                "error_type": type(exc).__name__,
                "raw_response": raw[:500],
            },
        )
        raise ClassificationError(
            f"Failed to parse normative classification response: {raw!r}"
        ) from exc

    # Numbered blocks are always normative; LLM handles the rest
    all_normative = numbered_indices | llm_indices
    logger.info(
        "normative_classification",
        extra={
            "total_blocks": len(blocks),
            "numbered": len(numbered_indices),
            "llm_selected": len(llm_indices),
            "total_normative": len(all_normative),
        },
    )
    return [b for i, b in enumerate(blocks) if i in all_normative]
