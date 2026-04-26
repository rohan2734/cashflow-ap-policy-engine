from shared_types.rules import RuleRecord, ConflictReport, ASTNode


def detect_conflicts(rules: list[RuleRecord]) -> list[ConflictReport]:
    numeric = [r for r in rules if _is_numeric(r.condition)]
    conflicts: list[ConflictReport] = []
    for i, r1 in enumerate(numeric):
        for r2 in numeric[i + 1:]:
            if r1.action != r2.action and _same_field(r1.condition, r2.condition):
                conflicts.append(ConflictReport(
                    rule_ids=[r1.rule_id, r2.rule_id],
                    overlap_description=(
                        f"{r1.rule_id} ({r1.action}) conflicts with {r2.rule_id} ({r2.action})"
                    ),
                ))
    return conflicts


def _is_numeric(node: ASTNode | str | float) -> bool:
    return isinstance(node, ASTNode) and node.op in {">", "<", ">=", "<="}


def _same_field(n1: ASTNode, n2: ASTNode) -> bool:
    return n1.left == n2.left
