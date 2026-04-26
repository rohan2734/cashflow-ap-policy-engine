from sqlalchemy import Column, String, Float, JSON, Boolean, Integer, ForeignKey, DateTime, func
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class LLMProviderModel(Base):
    __tablename__ = "llm_providers"
    provider_id = Column(String, primary_key=True)
    name        = Column(String, nullable=False)
    type        = Column(String, nullable=False)   # nvidia | bedrock | openrouter
    config      = Column(JSON, nullable=False)
    # config: { model, temperature, max_tokens, base_url, ... }
    # shape differs per provider type — JSONB avoids forcing a shared schema
    active      = Column(Boolean, nullable=False, default=True)

class PromptModel(Base):
    __tablename__ = "prompts"
    prompt_id          = Column(String, primary_key=True)
    name               = Column(String, nullable=False)
    version            = Column(Integer, nullable=False)
    langfuse_prompt_id = Column(String, nullable=True)   # set after Langfuse is wired
    # Langfuse is source of truth for content + version history.
    # DB owns which (name, version) is active for a given pipeline.
    active             = Column(Boolean, nullable=False, default=True)

class PipelineModel(Base):
    __tablename__ = "pipelines"
    pipeline_id     = Column(String, primary_key=True)
    name            = Column(String, nullable=False)
    llm_provider_id = Column(String, ForeignKey("llm_providers.provider_id"), nullable=False)
    prompt_id       = Column(String, ForeignKey("prompts.prompt_id"), nullable=False)
    config          = Column(JSON, nullable=False)
    # config: { confidence_threshold, concurrency, notification_endpoint }
    # confidence_threshold: rules below this value → status=pending_review
    # All pipeline-level settings go here; new keys need no migration.
    active          = Column(Boolean, nullable=False, default=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

class DocumentModel(Base):
    __tablename__ = "documents"
    doc_id      = Column(String, primary_key=True)
    filename    = Column(String, nullable=False)
    pipeline_id = Column(String, ForeignKey("pipelines.pipeline_id"), nullable=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

class RuleModel(Base):
    __tablename__ = "rules"
    rule_id         = Column(String, primary_key=True)
    doc_id          = Column(String, ForeignKey("documents.doc_id"), nullable=False)
    condition       = Column(JSON, nullable=False)
    action          = Column(String, nullable=False)
    confidence      = Column(Float, nullable=False)
    source_clauses  = Column(JSON, nullable=False)
    status          = Column(String, nullable=False, default="auto_approved")
    # status values: auto_approved | pending_review | reviewed
    override_action = Column(String, nullable=True)

class ConflictModel(Base):
    __tablename__ = "conflicts"
    conflict_id         = Column(String, primary_key=True)
    doc_id              = Column(String, ForeignKey("documents.doc_id"), nullable=False)
    rule_ids            = Column(JSON, nullable=False)
    overlap_description = Column(String, nullable=False)

class ExecutionModel(Base):
    __tablename__ = "executions"
    execution_id       = Column(String, primary_key=True)
    invoice_id         = Column(String, nullable=False)
    doc_id             = Column(String, ForeignKey("documents.doc_id"), nullable=False)
    decision           = Column(String, nullable=False)
    triggered_rule_ids = Column(JSON, nullable=False)
    reasons            = Column(JSON, nullable=False)
    executed_at        = Column(DateTime(timezone=True), server_default=func.now())