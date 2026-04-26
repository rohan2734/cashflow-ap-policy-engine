from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ASTNode:
    op: str
    left: ASTNode | str | float
    right: ASTNode | str | float | None

@dataclass(frozen=True)
class RuleRecord:
    rule_id: str
    doc_id: str
    condition: ASTNode
    action: str
    confidence: float
    source_clauses: list[str]

@dataclass(frozen=True)
class ConflictReport:
    rule_ids: list[str]
    overlap_description: str