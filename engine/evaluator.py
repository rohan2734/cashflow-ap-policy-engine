from typing import Any
from shared_types.rules import ASTNode
from shared_types.invoice import InvoiceRecord


class EvaluationError(Exception):
    pass


def evaluate_node(node: ASTNode | str | float | int, invoice: InvoiceRecord) -> Any:
    if isinstance(node, str):
        return invoice.fields.get(node, node)
    if isinstance(node, (int, float)):
        return node
    if not isinstance(node, ASTNode):
        raise EvaluationError(f"Unexpected node type: {type(node)!r}")
    left = evaluate_node(node.left, invoice)
    right = evaluate_node(node.right, invoice) if node.right is not None else None
    match node.op:
        case ">":
            return left > right
        case "<":
            return left < right
        case ">=":
            return left >= right
        case "<=":
            return left <= right
        case "==":
            return left == right
        case "*":
            return left * right
        case "+":
            return left + right
        case "AND":
            return bool(left) and bool(right)
        case "OR":
            return bool(left) or bool(right)
        case "NOT":
            return not bool(left)
        case _:
            raise EvaluationError(f"Unknown op: {node.op!r}")