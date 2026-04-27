import asyncio
import json
import logging

from shared_types.pipeline import EnrichedClause, RawExtraction, ValidatedExtraction
from shared_types.rules import RuleRecord
from pipeline.parser import parse_pdf
from pipeline.clause_classifier import classify_normative_blocks
from pipeline.splitter import split_into_clauses
from pipeline.xref_resolver import resolve_references
from pipeline.llm_extractor import extract_clause, ExtractionError
from pipeline.validator import validate_extraction, ValidationError, VALID_ACTIONS, VALID_OPS
from pipeline.rule_builder import build_rule
from pipeline.conflict_detector import detect_numeric_conflicts, detect_logical_conflicts
from llm.client import LLMClient, LLMCallError
from llm.prompts import RETRY_EXTRACTION_PROMPT
from llm.tracing import get_langfuse, set_trace_context
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
    langfuse = get_langfuse()
    trace = langfuse.trace(
        name="run_pipeline",
        metadata={
            "doc_id": doc_id,
            "pipeline_id": config.pipeline_id,
            "provider": config.llm.provider,
            "model": config.llm.model,
        },
    )

    set_trace_context(doc_id=doc_id, pipeline_id=config.pipeline_id)

    logger.info(
        "pipeline_start",
        extra={
            "doc_id": doc_id,
            "pipeline_id": config.pipeline_id,
            "file_path": file_path,
            "provider": config.llm.provider,
            "model": config.llm.model,
        },
    )

    with trace.span(name="parse_pdf"):
        logger.debug("pipeline_stage_parse_pdf_start", extra={"doc_id": doc_id})
        blocks = parse_pdf(file_path)
        logger.info(
            "pipeline_stage_parse_pdf_complete",
            extra={"doc_id": doc_id, "blocks_count": len(blocks)},
        )

    with trace.span(name="classify_normative_blocks"):
        logger.debug("pipeline_stage_classify_start", extra={"doc_id": doc_id})
        normative_blocks = await classify_normative_blocks(blocks, llm)
        logger.info(
            "pipeline_stage_classify_complete",
            extra={
                "doc_id": doc_id,
                "total_blocks": len(blocks),
                "normative_blocks": len(normative_blocks),
            },
        )

    with trace.span(name="split_into_clauses"):
        logger.debug("pipeline_stage_split_start", extra={"doc_id": doc_id})
        clauses = split_into_clauses(normative_blocks)
        logger.info(
            "pipeline_stage_split_complete",
            extra={"doc_id": doc_id, "clauses_count": len(clauses)},
        )

    with trace.span(name="resolve_references"):
        logger.debug("pipeline_stage_resolve_start", extra={"doc_id": doc_id})
        enriched = resolve_references(clauses)
        logger.info(
            "pipeline_stage_resolve_complete",
            extra={
                "doc_id": doc_id,
                "clauses_count": len(enriched),
                "total_references": sum(len(c.referenced_clauses) for c in enriched),
            },
        )

    with trace.span(name="extract_rules"):
        logger.debug(
            "pipeline_stage_extract_start",
            extra={
                "doc_id": doc_id,
                "clauses_count": len(enriched),
                "max_parallel": config.concurrency.max_parallel_clauses,
            },
        )
        sem = asyncio.Semaphore(config.concurrency.max_parallel_clauses)
        results = await asyncio.gather(*[_process(c, doc_id, config, llm, sem) for c in enriched])
        rules = [r for r in results if r is not None]
        logger.info(
            "pipeline_stage_extract_complete",
            extra={
                "doc_id": doc_id,
                "total_clauses": len(enriched),
                "successful_extractions": len(rules),
                "failed_extractions": len(enriched) - len(rules),
            },
        )

    with trace.span(name="detect_conflicts"):
        logger.debug("pipeline_stage_conflict_start", extra={"doc_id": doc_id})
        numeric_conflicts = detect_numeric_conflicts(rules)
        logical_conflicts = await detect_logical_conflicts(rules, llm)
        conflicts = numeric_conflicts + logical_conflicts
        logger.info(
            "pipeline_stage_conflict_complete",
            extra={
                "doc_id": doc_id,
                "numeric_conflicts": len(numeric_conflicts),
                "logical_conflicts": len(logical_conflicts),
                "total_conflicts": len(conflicts),
            },
        )

    with trace.span(name="persist_results"):
        logger.debug("pipeline_stage_persist_start", extra={"doc_id": doc_id})
        async with db.session() as session:
            threshold = config.confidence_threshold
            auto_approved = 0
            pending_review = 0
            for rule in rules:
                status = "pending_review" if rule.confidence < threshold else "auto_approved"
                if status == "auto_approved":
                    auto_approved += 1
                else:
                    pending_review += 1
                await queries.insert_rule(session, rule, status=status)
            for conflict in conflicts:
                await queries.insert_conflict(session, doc_id, conflict)
            await session.commit()
        logger.info(
            "pipeline_stage_persist_complete",
            extra={
                "doc_id": doc_id,
                "auto_approved": auto_approved,
                "pending_review": pending_review,
                "conflicts": len(conflicts),
            },
        )

    trace.end(output={"rules_count": len(rules), "conflicts_count": len(conflicts)})
    logger.info(
        "pipeline_complete",
        extra={
            "doc_id": doc_id,
            "rules_count": len(rules),
            "conflicts_count": len(conflicts),
            "auto_approved": auto_approved,
            "pending_review": pending_review,
        },
    )

    return rules


async def _process(
    clause: EnrichedClause,
    doc_id: str,
    config: AppConfig,
    llm: LLMClient,
    sem: asyncio.Semaphore,
) -> RuleRecord | None:
    async with sem:
        logger.debug(
            "clause_extraction_start",
            extra={
                "doc_id": doc_id,
                "clause_id": clause.id,
                "page": clause.page,
                "text_length": len(clause.text),
                "references_count": len(clause.referenced_clauses),
            },
        )

        raw: RawExtraction | None = None
        try:
            raw = await extract_clause(clause, llm, config.llm)
            validated = validate_extraction(raw)
            logger.debug(
                "clause_extraction_success",
                extra={
                    "doc_id": doc_id,
                    "clause_id": clause.id,
                    "confidence": validated.confidence,
                    "action": validated.action,
                },
            )
        except (ExtractionError, ValidationError, LLMCallError) as exc:
            logger.warning(
                "extraction_retry",
                extra={
                    "doc_id": doc_id,
                    "clause_id": clause.id,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )
            try:
                retry_prompt = RETRY_EXTRACTION_PROMPT.format(
                    clause_text=clause.text,
                    previous_action=raw.action_raw if raw else "unknown",
                    previous_condition=json.dumps(raw.condition_raw) if raw else "{}",
                    error=str(exc),
                    valid_actions=", ".join(sorted(VALID_ACTIONS)),
                    valid_ops=", ".join(sorted(VALID_OPS)),
                )
                text = await llm.generate(retry_prompt)
                parsed = json.loads(text.strip())
                raw = RawExtraction(
                    clause_id=clause.id,
                    condition_raw=parsed.get("condition", {}),
                    action_raw=parsed.get("action", ""),
                    exceptions_raw=parsed.get("exceptions", []),
                    confidence_raw=float(parsed.get("confidence", 0.5)),
                )
                v = validate_extraction(raw)
                validated = ValidatedExtraction(
                    clause_id=v.clause_id,
                    condition=v.condition,
                    action=v.action,
                    exceptions=v.exceptions,
                    confidence=min(v.confidence, 0.5),
                )
                logger.info(
                    "extraction_retry_success",
                    extra={
                        "doc_id": doc_id,
                        "clause_id": clause.id,
                        "confidence": validated.confidence,
                        "action": validated.action,
                    },
                )
            except (json.JSONDecodeError, ValidationError, LLMCallError) as retry_exc:
                logger.warning(
                    "extraction_failed",
                    extra={
                        "doc_id": doc_id,
                        "clause_id": clause.id,
                        "error": str(retry_exc),
                        "error_type": type(retry_exc).__name__,
                    },
                )
                return None

        return build_rule(validated, doc_id)
