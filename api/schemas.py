from pydantic import BaseModel
from typing import Any


class UploadResponse(BaseModel):
    doc_id: str
    rule_count: int
    conflict_count: int


class RuleResponse(BaseModel):
    rule_id: str
    action: str
    confidence: float
    source_clauses: list[str]
    condition: dict[str, Any]


class RulesListResponse(BaseModel):
    doc_id: str
    rules: list[RuleResponse]


class ExecuteRequest(BaseModel):
    doc_id: str
    invoice: dict[str, Any]


class ExecuteResponse(BaseModel):
    decision: str
    triggered_rule_ids: list[str]
    reasons: list[str]


class PatchRuleRequest(BaseModel):
    override_action: str  # APPROVE | ESCALATE | REJECT


class ReviewRuleResponse(BaseModel):
    rule_id: str
    doc_id: str
    action: str
    confidence: float
    source_clauses: list[str]
    condition: dict[str, Any]
    status: str
    override_action: str | None


class ReviewQueueResponse(BaseModel):
    rules: list[ReviewRuleResponse]


class ReviewThresholdResponse(BaseModel):
    threshold: float


class ReviewThresholdRequest(BaseModel):
    threshold: float


class PipelineConfigResponse(BaseModel):
    pipeline_id: str
    name: str
    config: dict[str, Any]


class PipelineConfigRequest(BaseModel):
    config: dict[str, Any]


class ProviderConfigResponse(BaseModel):
    provider_id: str
    name: str
    type: str
    config: dict[str, Any]


class ProviderConfigRequest(BaseModel):
    config: dict[str, Any]


class ProviderListItemResponse(BaseModel):
    provider_id: str
    name: str
    type: str
    config: dict[str, Any]
    is_active: bool


class ProvidersListResponse(BaseModel):
    providers: list[ProviderListItemResponse]
