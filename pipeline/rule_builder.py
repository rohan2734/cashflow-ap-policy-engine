import uuid
from shared_types.pipeline import ValidatedExtraction
from shared_types.rules import ASTNode, RuleRecord


class ASTBuildError(Exception):
    pass


def build_rule(validated: ValidatedExtraction, doc_id: str) -> RuleRecord:
    return RuleRecord(
        rule_id=f"R-{uuid.uuid4().hex[:8].upper()}",
        doc_id=doc_id,
        condition=_build_ast(validated.condition, validated.clause_id),
        action=validated.action,
        confidence=validated.confidence,
        source_clauses=[validated.clause_id],
    )


def _build_ast(node: dict | str | float | int, clause_id: str) -> ASTNode | str | float:
    if not isinstance(node, dict):
        return node
    op = node.get("op")
    if not op:
        raise ASTBuildError(f"Node missing 'op' in {clause_id!r}: {node!r}")
    left = _build_ast(node.get("left", ""), clause_id)
    right = _build_ast(node["right"], clause_id) if "right" in node else None
    return ASTNode(op=op, left=left, right=right)
