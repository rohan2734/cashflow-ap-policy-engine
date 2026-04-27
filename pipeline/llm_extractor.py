import json
import logging
import re

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

    logger.info(
        "extract_clause_llm_response_received",
        extra={
            "clause_id": clause.id,
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
    except json.JSONDecodeError as exc:
        logger.error(
            "extract_clause_parse_error",
            extra={
                "clause_id": clause.id,
                "error": str(exc),
                "error_message": exc.msg,
                "error_line": exc.lineno,
                "error_column": exc.colno,
                "raw_response_length": len(raw),
                "raw_response": raw,
                "json_attempt": json_str if 'json_str' in locals() else "N/A",
                "json_attempt_length": len(json_str) if 'json_str' in locals() else 0,
            },
        )
        raise ExtractionError(f"JSON parse failed for clause {clause.id!r}: {exc.msg} at line {exc.lineno}, column {exc.colno}") from exc

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
            "action_length": len(result.action_raw) if result.action_raw else 0,
            "confidence": result.confidence_raw,
            "has_condition": bool(result.condition_raw),
            "condition_preview": str(result.condition_raw)[:200] if result.condition_raw else "None",
            "exceptions_count": len(result.exceptions_raw),
            "exceptions_preview": str(result.exceptions_raw)[:200] if result.exceptions_raw else "None",
            "parsed_json_keys": list(parsed.keys()),
        },
    )

    return result
