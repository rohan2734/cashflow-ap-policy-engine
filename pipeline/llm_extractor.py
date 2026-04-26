import json
from shared_types.pipeline import EnrichedClause, RawExtraction
from llm.client import LLMClient
from llm.prompts import EXTRACTION_PROMPT
from config.types import LLMConfig


class ExtractionError(Exception):
    pass


async def extract_clause(clause: EnrichedClause, llm: LLMClient, config: LLMConfig) -> RawExtraction:
    context = clause.text
    if clause.referenced_texts:
        context += "\n\nReferenced:\n" + "\n".join(clause.referenced_texts)
    raw = await llm.generate(EXTRACTION_PROMPT.format(clause_text=context))
    try:
        parsed = json.loads(raw.strip().strip("```json").strip("```").strip())
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"JSON parse failed for clause {clause.id!r}") from exc
    return RawExtraction(
        clause_id=clause.id,
        condition_raw=parsed.get("condition", {}),
        action_raw=parsed.get("action", ""),
        exceptions_raw=parsed.get("exceptions", []),
    )
