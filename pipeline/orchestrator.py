import asyncio, json, logging
from shared_types.pipeline import EnrichedClause, RawExtraction, ValidatedExtraction
from shared_types.rules import RuleRecord
from pipeline.parser import parse_pdf
from pipeline.splitter import split_into_clauses
from pipeline.xref_resolver import resolve_references
from pipeline.llm_extractor import extract_clause, ExtractionError
from pipeline.validator import validate_extraction, ValidationError
from pipeline.rule_builder import build_rule
from pipeline.conflict_detector import detect_conflicts
from llm.client import LLMClient
from llm.prompts import RETRY_EXTRACTION_PROMPT
from config.types import AppConfig
from db.connector import DBConnector
from db import queries

logger = logging.getLogger(__name__)

async def run_pipeline(
    file_path: str,
    doc_id: str,
    config: AppConfig,
    llm: LLMClient,
    db: DBConnector,
) -> list[RuleRecord]:
    blocks = parse_pdf(file_path)
    clauses = split_into_clauses(blocks)
    enriched = resolve_references(clauses)

    sem = asyncio.Semaphore(config.concurrency.max_parallel_clauses)
    results = await asyncio.gather(*[_process(c, doc_id, config, llm, sem) for c in enriched])
    rules = [r for r in results if r is not None]
    conflicts = detect_conflicts(rules)

    async with db.session() as session:
        threshold = config.confidence_threshold
        for rule in rules:
            status = "pending_review" if rule.confidence < threshold else "auto_approved"
            await queries.insert_rule(session, rule, status=status)
        for conflict in conflicts:
            await queries.insert_conflict(session, doc_id, conflict)
        await session.commit()

    return rules

async def _process(
    clause: EnrichedClause,
    doc_id: str,
    config: AppConfig,
    llm: LLMClient,
    sem: asyncio.Semaphore,
) -> RuleRecord | None:
    async with sem:
        try:
            raw = await extract_clause(clause, llm, config.llm)
            validated = validate_extraction(raw)
        except (ExtractionError, ValidationError) as exc:
            logger.warning("extraction_retry", extra={"clause_id": clause.id, "error": str(exc)})
            try:
                text = await llm.generate(RETRY_EXTRACTION_PROMPT.format(clause_text=clause.text))
                parsed = json.loads(text.strip())
                raw = RawExtraction(
                    clause_id=clause.id,
                    condition_raw=parsed.get("condition", {}),
                    action_raw=parsed.get("action", ""),
                    exceptions_raw=parsed.get("exceptions", []),
                )
                v = validate_extraction(raw)
                validated = ValidatedExtraction(
                    clause_id=v.clause_id, condition=v.condition,
                    action=v.action, exceptions=v.exceptions, confidence=0.5,
                )
            except Exception as retry_exc:
                logger.warning("extraction_failed", extra={"clause_id": clause.id, "error": str(retry_exc)})
                return None

        return build_rule(validated, doc_id)