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
    if not blocks:
        return []

    numbered_indices = {i for i, b in enumerate(blocks) if _NUMBERED.match(b.text)}

    blocks_text = "\n".join(
        f"{i}: {b.text[:_BLOCK_PREVIEW_CHARS]}" for i, b in enumerate(blocks)
    )
    raw = await llm.generate(CLASSIFY_PROMPT.format(blocks=blocks_text))

    try:
        parsed = json.loads(raw.strip())
        llm_indices = set(parsed["normative_indices"])
    except (json.JSONDecodeError, KeyError) as exc:
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
