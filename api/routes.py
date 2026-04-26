import os, uuid, dataclasses
from fastapi import APIRouter, UploadFile, HTTPException
from api.schemas import (
    UploadResponse, RulesListResponse, ExecuteRequest, ExecuteResponse,
    PatchRuleRequest, ReviewQueueResponse, ReviewRuleResponse,
    ReviewThresholdResponse, ReviewThresholdRequest,
    PipelineConfigResponse, PipelineConfigRequest,
    ProviderConfigResponse, ProviderConfigRequest,
)
from api.dependencies import get_config, get_llm, get_db, set_config
from pipeline.orchestrator import run_pipeline
from pipeline.conflict_detector import detect_conflicts
from engine.executor import execute_rules
from notifications.dispatcher import dispatch
from db import queries
from shared_types.invoice import InvoiceRecord
from config.loader import load_config_from_db

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload_policy(file: UploadFile):
    config = get_config()
    llm = get_llm()
    db = get_db()
    doc_id = f"DOC-{uuid.uuid4().hex[:8].upper()}"
    tmp = f"/tmp/{doc_id}.pdf"
    try:
        with open(tmp, "wb") as f:
            f.write(await file.read())
        async with db.session() as session:
            await queries.insert_document(session, doc_id, file.filename or "unknown.pdf", config.pipeline_id)
            await session.commit()
        rules = await run_pipeline(tmp, doc_id, config, llm, db)
        conflicts = detect_conflicts(rules)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return UploadResponse(doc_id=doc_id, rule_count=len(rules), conflict_count=len(conflicts))


@router.get("/rules/{doc_id}", response_model=RulesListResponse)
async def get_rules(doc_id: str):
    db = get_db()
    async with db.session() as session:
        rules = await queries.fetch_rules_by_doc(session, doc_id)
    if not rules:
        raise HTTPException(404, f"No rules for doc_id={doc_id!r}")
    return RulesListResponse(
        doc_id=doc_id,
        rules=[
            {"rule_id": r.rule_id, "action": r.action, "confidence": r.confidence,
             "source_clauses": r.source_clauses, "condition": dataclasses.asdict(r.condition)}
            for r in rules
        ],
    )


@router.post("/execute", response_model=ExecuteResponse)
async def execute(body: ExecuteRequest):
    config = get_config()
    db = get_db()
    async with db.session() as session:
        rules = await queries.fetch_rules_by_doc(session, body.doc_id)
    if not rules:
        raise HTTPException(404, f"No rules for doc_id={body.doc_id!r}")
    invoice = InvoiceRecord(
        invoice_id=body.invoice.get("invoice_id", f"INV-{uuid.uuid4().hex[:8]}"),
        fields=body.invoice,
    )
    result = execute_rules(rules, invoice, body.doc_id)
    async with db.session() as session:
        await queries.insert_execution(session, result)
        await session.commit()
    await dispatch(result, config.notifications)
    return ExecuteResponse(
        decision=result.decision,
        triggered_rule_ids=result.triggered_rule_ids,
        reasons=result.reasons,
    )


@router.get("/review", response_model=ReviewQueueResponse)
async def get_review_queue():
    db = get_db()
    async with db.session() as session:
        rows = await queries.fetch_pending_review_rules(session)
    return ReviewQueueResponse(rules=[
        ReviewRuleResponse(
            rule_id=r.rule_id, doc_id=r.doc_id, action=r.action,
            confidence=r.confidence, source_clauses=r.source_clauses,
            condition=r.condition, status=r.status, override_action=r.override_action,
        )
        for r in rows
    ])


@router.patch("/rules/{rule_id}", response_model=ReviewRuleResponse)
async def patch_rule(rule_id: str, body: PatchRuleRequest):
    if body.override_action not in {"APPROVE", "ESCALATE", "REJECT"}:
        raise HTTPException(400, f"Invalid action: {body.override_action!r}")
    db = get_db()
    async with db.session() as session:
        try:
            await queries.update_rule_review(session, rule_id, body.override_action)
            await session.commit()
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        row = await queries.fetch_rule_by_id(session, rule_id)
    return ReviewRuleResponse(
        rule_id=row.rule_id, doc_id=row.doc_id, action=row.action,
        confidence=row.confidence, source_clauses=row.source_clauses,
        condition=row.condition, status=row.status, override_action=row.override_action,
    )


@router.get("/settings/review-threshold", response_model=ReviewThresholdResponse)
async def get_review_threshold():
    return ReviewThresholdResponse(threshold=get_config().confidence_threshold)


@router.patch("/settings/review-threshold", response_model=ReviewThresholdResponse)
async def set_review_threshold(body: ReviewThresholdRequest):
    if not (0.0 <= body.threshold <= 1.0):
        raise HTTPException(400, "threshold must be between 0.0 and 1.0")
    config = get_config()
    db = get_db()
    async with db.session() as session:
        pipeline = await queries.fetch_active_pipeline(session)
        updated_pipeline_config = {**pipeline.config, "confidence_threshold": body.threshold}
        await queries.update_pipeline_config(session, config.pipeline_id, updated_pipeline_config)
        await session.commit()
        updated_config = await load_config_from_db(session)
        set_config(updated_config)
    return ReviewThresholdResponse(threshold=body.threshold)


@router.get("/config/pipeline", response_model=PipelineConfigResponse)
async def get_pipeline_config():
    db = get_db()
    async with db.session() as session:
        pipeline = await queries.fetch_active_pipeline(session)
    return PipelineConfigResponse(
        pipeline_id=pipeline.pipeline_id,
        name=pipeline.name,
        config=pipeline.config,
    )


@router.patch("/config/pipeline", response_model=PipelineConfigResponse)
async def update_pipeline_config(body: PipelineConfigRequest):
    config = get_config()
    db = get_db()
    async with db.session() as session:
        pipeline = await queries.update_pipeline_config(session, config.pipeline_id, body.config)
        await session.commit()
        updated_config = await load_config_from_db(session)
        set_config(updated_config)
    return PipelineConfigResponse(
        pipeline_id=pipeline.pipeline_id,
        name=pipeline.name,
        config=pipeline.config,
    )


@router.get("/config/provider", response_model=ProviderConfigResponse)
async def get_provider_config():
    db = get_db()
    async with db.session() as session:
        pipeline = await queries.fetch_active_pipeline(session)
        provider = await queries.fetch_provider(session, pipeline.llm_provider_id)
    return ProviderConfigResponse(
        provider_id=provider.provider_id,
        name=provider.name,
        type=provider.type,
        config=provider.config,
    )


@router.patch("/config/provider", response_model=ProviderConfigResponse)
async def update_provider_config(body: ProviderConfigRequest):
    db = get_db()
    async with db.session() as session:
        pipeline = await queries.fetch_active_pipeline(session)
        provider = await queries.update_provider_config(session, pipeline.llm_provider_id, body.config)
        await session.commit()
        updated_config = await load_config_from_db(session)
        set_config(updated_config)
    return ProviderConfigResponse(
        provider_id=provider.provider_id,
        name=provider.name,
        type=provider.type,
        config=provider.config,
    )
