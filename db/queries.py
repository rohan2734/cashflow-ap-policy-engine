import uuid, dataclasses
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import (
    DocumentModel, RuleModel, ConflictModel, ExecutionModel,
    LLMProviderModel, PromptModel, PipelineModel,
)
from shared_types.rules import RuleRecord, ConflictReport, ASTNode
from shared_types.invoice import ExecutionResult

# ── provider / prompt / pipeline ─────────────────────────────────────────────

async def fetch_active_pipeline(session: AsyncSession) -> PipelineModel:
    result = await session.execute(select(PipelineModel).where(PipelineModel.active == True))
    row = result.scalar_one_or_none()
    if row is None:
        raise RuntimeError("No active pipeline found — run seeder first")
    return row

async def fetch_provider(session: AsyncSession, provider_id: str) -> LLMProviderModel:
    result = await session.execute(
        select(LLMProviderModel).where(LLMProviderModel.provider_id == provider_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise KeyError(f"provider_id={provider_id!r} not found")
    return row

async def fetch_prompt(session: AsyncSession, prompt_id: str) -> PromptModel:
    result = await session.execute(
        select(PromptModel).where(PromptModel.prompt_id == prompt_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise KeyError(f"prompt_id={prompt_id!r} not found")
    return row

async def update_pipeline_config(
    session: AsyncSession, pipeline_id: str, config: dict
) -> PipelineModel:
    result = await session.execute(
        select(PipelineModel).where(PipelineModel.pipeline_id == pipeline_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise KeyError(f"pipeline_id={pipeline_id!r} not found")
    row.config = config
    return row

async def update_provider_config(
    session: AsyncSession, provider_id: str, config: dict
) -> LLMProviderModel:
    result = await session.execute(
        select(LLMProviderModel).where(LLMProviderModel.provider_id == provider_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise KeyError(f"provider_id={provider_id!r} not found")
    row.config = config
    return row

# ── documents / rules / conflicts / executions ───────────────────────────────

async def insert_document(
    session: AsyncSession, doc_id: str, filename: str, pipeline_id: str
) -> None:
    session.add(DocumentModel(doc_id=doc_id, filename=filename, pipeline_id=pipeline_id))

async def insert_rule(session: AsyncSession, rule: RuleRecord, status: str) -> None:
    session.add(RuleModel(
        rule_id=rule.rule_id,
        doc_id=rule.doc_id,
        condition=dataclasses.asdict(rule.condition),
        action=rule.action,
        confidence=rule.confidence,
        source_clauses=rule.source_clauses,
        status=status,
    ))

async def insert_conflict(session: AsyncSession, doc_id: str, report: ConflictReport) -> None:
    session.add(ConflictModel(
        conflict_id=f"C-{uuid.uuid4().hex[:8].upper()}",
        doc_id=doc_id,
        rule_ids=report.rule_ids,
        overlap_description=report.overlap_description,
    ))

async def fetch_rules_by_doc(session: AsyncSession, doc_id: str) -> list[RuleRecord]:
    result = await session.execute(select(RuleModel).where(RuleModel.doc_id == doc_id))
    return [_row_to_rule(row) for row in result.scalars().all()]

async def insert_execution(session: AsyncSession, result: ExecutionResult) -> None:
    session.add(ExecutionModel(
        execution_id=f"E-{uuid.uuid4().hex[:8].upper()}",
        invoice_id=result.invoice_id,
        doc_id=result.doc_id,
        decision=result.decision,
        triggered_rule_ids=result.triggered_rule_ids,
        reasons=result.reasons,
    ))

async def fetch_rule_by_id(session: AsyncSession, rule_id: str) -> RuleModel | None:
    result = await session.execute(select(RuleModel).where(RuleModel.rule_id == rule_id))
    return result.scalar_one_or_none()

async def fetch_pending_review_rules(session: AsyncSession) -> list[RuleModel]:
    result = await session.execute(select(RuleModel).where(RuleModel.status == "pending_review"))
    return list(result.scalars().all())

async def update_rule_review(
    session: AsyncSession, rule_id: str, override_action: str,
) -> None:
    result = await session.execute(select(RuleModel).where(RuleModel.rule_id == rule_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise KeyError(f"rule_id={rule_id!r} not found")
    row.override_action = override_action
    row.status = "reviewed"

# ── helpers ───────────────────────────────────────────────────────────────────

def _row_to_rule(row: RuleModel) -> RuleRecord:
    return RuleRecord(
        rule_id=row.rule_id,
        doc_id=row.doc_id,
        condition=_dict_to_ast(row.condition),
        action=row.action,
        confidence=row.confidence,
        source_clauses=row.source_clauses,
    )

def _dict_to_ast(d: dict) -> ASTNode:
    left = d["left"]
    right = d.get("right")
    return ASTNode(
        op=d["op"],
        left=_dict_to_ast(left) if isinstance(left, dict) else left,
        right=_dict_to_ast(right) if isinstance(right, dict) else right,
    )