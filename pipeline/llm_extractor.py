import json
import logging

from shared_types.pipeline import EnrichedClause, RawExtraction
from llm.client import LLMClient
from llm.prompts import EXTRACTION_PROMPT
from config.types import LLMConfig

logger = logging.getLogger(__name__)


class ExtractionError(Exception):
    pass


async def extract_clause(clause: EnrichedClause, llm: LLMClient, config: LLMConfig) -> RawExtraction:
    logger.debug(
        "extract_clause_start",
        extra={
            "clause_id": clause.id,
            "page": clause.page,
            "text_length": len(clause.text),
            "references_count": len(clause.referenced_clauses),
        },
    )

    context = clause.text
    if clause.referenced_clauses:
        refs = "\n".join(f"[{ref.id}]: {ref.text}" for ref in clause.referenced_clauses)
        context += f"\n\nReferenced Clauses (cited in the text above):\n{refs}"
        logger.debug(
            "extract_clause_with_references",
            extra={
                "clause_id": clause.id,
                "references": [ref.id for ref in clause.referenced_clauses],
            },
        )

    logger.debug(
        "extract_clause_llm_call",
        extra={
            "clause_id": clause.id,
            "context_length": len(context),
        },
    )

    raw = await llm.generate(EXTRACTION_PROMPT.format(clause_text=context))

    logger.debug(
        "extract_clause_llm_response",
        extra={
            "clause_id": clause.id,
            "response_length": len(raw),
        },
    )

    try:
        parsed = json.loads(raw.strip().strip("```json").strip("```").strip())
    except json.JSONDecodeError as exc:
        logger.error(
            "extract_clause_parse_error",
            extra={
                "clause_id": clause.id,
                "error": str(exc),
                "raw_response": raw[:500],
            },
        )
        raise ExtractionError(f"JSON parse failed for clause {clause.id!r}: {raw!r}") from exc

    result = RawExtraction(
        clause_id=clause.id,
        condition_raw=parsed.get("condition", {}),
        action_raw=parsed.get("action", ""),
        exceptions_raw=parsed.get("exceptions", []),
        confidence_raw=float(parsed.get("confidence", 0.5)),
    )

    logger.info(
        "extract_clause_success",
        extra={
            "clause_id": clause.id,
            "action": result.action_raw,
            "confidence": result.confidence_raw,
            "has_condition": bool(result.condition_raw),
            "exceptions_count": len(result.exceptions_raw),
        },
    )

    return result
