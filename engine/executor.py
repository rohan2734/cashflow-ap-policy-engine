from shared_types.rules import RuleRecord
from shared_types.invoice import InvoiceRecord, ExecutionResult
from engine.evaluator import evaluate_node


PRIORITY = {"REJECT": 3, "ESCALATE": 2, "APPROVE": 1}


def execute_rules(rules: list[RuleRecord], invoice: InvoiceRecord, doc_id: str) -> ExecutionResult:
    triggered = [r for r in rules if _matches(r, invoice)]
    if not triggered:
        return ExecutionResult(
            invoice_id=invoice.invoice_id, doc_id=doc_id,
            decision="APPROVE", triggered_rule_ids=[], reasons=["No rules triggered"],
        )
    winner = max(triggered, key=lambda r: PRIORITY[r.action])
    return ExecutionResult(
        invoice_id=invoice.invoice_id, doc_id=doc_id,
        decision=winner.action,
        triggered_rule_ids=[r.rule_id for r in triggered],
        reasons=[f"{r.rule_id} matched ({r.action})" for r in triggered],
    )


def _matches(rule: RuleRecord, invoice: InvoiceRecord) -> bool:
    try:
        return bool(evaluate_node(rule.condition, invoice))
    except Exception:
        return False