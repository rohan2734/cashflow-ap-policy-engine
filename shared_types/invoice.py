from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class InvoiceRecord:
    invoice_id: str
    fields: dict[str, Any]

@dataclass(frozen=True)
class ExecutionResult:
    invoice_id: str
    doc_id: str
    decision: str
    triggered_rule_ids: list[str]
    reasons: list[str]