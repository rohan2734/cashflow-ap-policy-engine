import json
import logging
import re

from shared_types.rules import RuleRecord, ConflictReport, ASTNode
from llm.client import LLMClient
from llm.prompts import CONFLICT_CHECK_PROMPT

logger = logging.getLogger(__name__)

# Maps LLM-generated field name variants to the canonical schema name
_FIELD_ALIASES: dict[str, str] = {
    "amount": "invoice_amount",
    "total": "invoice_amount",
    "invoice_total": "invoice_amount",
    "inv_amount": "invoice_amount",
    "invoice_value": "invoice_amount",
    "total_amount": "invoice_amount",
    "age": "invoice_age_days",
    "days_old": "invoice_age_days",
    "invoice_age": "invoice_age_days",
    "vendor": "vendor_status",
    "vendor_state": "vendor_status",
    "tier": "vendor_tier",
    "vendor_level": "vendor_tier",
    "payment_days": "payment_terms_days",
    "terms": "payment_terms_days",
    "category": "expense_category",
    "type": "expense_category",
    "approval": "approval_level",
    "approver": "approval_level",
    "contract": "contract_status",
    "po": "po_matched",
    "po_number": "po_matched",
    "purchase_order": "po_matched",
}

_NUMERIC_OPS = {">", "<", ">=", "<="}
_COMPOUND_OPS = {"AND", "OR", "NOT"}


async def detect_conflicts(rules: list[RuleRecord], llm: LLMClient | None = None) -> list[ConflictReport]:
    """
    Detect both numeric and logical conflicts in rules.

    Args:
        rules: List of rules to check for conflicts
        llm: Optional LLM client for logical conflict detection

    Returns:
        Combined list of conflict reports from both detection methods
    """
    conflicts = detect_numeric_conflicts(rules)

    if llm is not None:
        try:
            logical_conflicts = await detect_logical_conflicts(rules, llm)
            conflicts.extend(logical_conflicts)
        except Exception as exc:
            logger.warning(
                "logical_conflict_detection_failed",
                extra={
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )

    return conflicts


def detect_numeric_conflicts(rules: list[RuleRecord]) -> list[ConflictReport]:
    logger.debug(
        "numeric_conflict_detection_start",
        extra={"total_rules": len(rules)},
    )

    simple_numeric = [r for r in rules if _is_simple_numeric(r.condition)]
    logger.debug(
        "numeric_conflict_simple_rules",
        extra={
            "total_rules": len(rules),
            "simple_numeric_rules": len(simple_numeric),
        },
    )

    by_field: dict[str, list[RuleRecord]] = {}
    for rule in simple_numeric:
        assert isinstance(rule.condition, ASTNode)
        field = _normalize_field(str(rule.condition.left))
        by_field.setdefault(field, []).append(rule)

    logger.debug(
        "numeric_conflict_fields",
        extra={"fields_count": len(by_field), "fields": list(by_field.keys())},
    )

    conflicts: list[ConflictReport] = []
    for field, group in by_field.items():
        conflicts.extend(_find_range_conflicts(field, group))

    logger.info(
        "numeric_conflict_detection_complete",
        extra={
            "total_rules": len(rules),
            "simple_numeric_rules": len(simple_numeric),
            "fields_checked": len(by_field),
            "conflicts_found": len(conflicts),
        },
    )

    return conflicts


async def detect_logical_conflicts(
    rules: list[RuleRecord], llm: LLMClient
) -> list[ConflictReport]:
    logger.debug(
        "logical_conflict_detection_start",
        extra={"total_rules": len(rules)},
    )

    compound = [r for r in rules if _is_compound(r.condition)]
    logger.debug(
        "logical_conflict_compound_rules",
        extra={
            "total_rules": len(rules),
            "compound_rules": len(compound),
        },
    )

    conflicts: list[ConflictReport] = []
    checks_performed = 0

    for i, r1 in enumerate(compound):
        for r2 in compound[i + 1:]:
            if r1.action == r2.action:
                continue
            if not _share_fields(r1.condition, r2.condition):
                continue
            checks_performed += 1
            report = await _llm_conflict_check(r1, r2, llm)
            if report:
                conflicts.append(report)

    logger.info(
        "logical_conflict_detection_complete",
        extra={
            "total_rules": len(rules),
            "compound_rules": len(compound),
            "checks_performed": checks_performed,
            "conflicts_found": len(conflicts),
        },
    )

    return conflicts


def _normalize_field(name: str) -> str:
    return _FIELD_ALIASES.get(name.lower(), name.lower())


def _is_simple_numeric(node: ASTNode | str | float) -> bool:
    return isinstance(node, ASTNode) and node.op in _NUMERIC_OPS


def _is_compound(node: ASTNode | str | float) -> bool:
    return isinstance(node, ASTNode) and node.op in _COMPOUND_OPS


def _extract_fields(node: ASTNode | str | float) -> set[str]:
    if not isinstance(node, ASTNode):
        return {_normalize_field(str(node))} if isinstance(node, str) else set()
    fields = _extract_fields(node.left)
    if node.right is not None:
        fields |= _extract_fields(node.right)
    return fields


def _share_fields(n1: ASTNode | str | float, n2: ASTNode | str | float) -> bool:
    return bool(_extract_fields(n1) & _extract_fields(n2))


def _find_range_conflicts(field: str, rules: list[RuleRecord]) -> list[ConflictReport]:
    """
    Detects overlapping numeric intervals with differing actions.

    Each rule contributes an interval based on its op and threshold.
    When two intervals overlap and prescribe different actions, it is a conflict.
    """
    intervals: list[tuple[float, float, bool, bool, RuleRecord]] = []
    for rule in rules:
        assert isinstance(rule.condition, ASTNode)
        op = rule.condition.op
        try:
            threshold = float(rule.condition.right)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        lo, hi, lo_inc, hi_inc = _op_to_interval(op, threshold)
        intervals.append((lo, hi, lo_inc, hi_inc, rule))

    conflicts: list[ConflictReport] = []
    for i, (lo1, hi1, li1, hi1_inc, r1) in enumerate(intervals):
        for lo2, hi2, li2, hi2_inc, r2 in intervals[i + 1:]:
            if r1.action == r2.action:
                continue
            if _intervals_overlap(lo1, hi1, li1, hi1_inc, lo2, hi2, li2, hi2_inc):
                conflicts.append(ConflictReport(
                    rule_ids=[r1.rule_id, r2.rule_id],
                    overlap_description=(
                        f"{r1.rule_id} ({r1.action}) and {r2.rule_id} ({r2.action}) "
                        f"overlap on field '{field}'"
                    ),
                ))
    return conflicts


def _op_to_interval(
    op: str, t: float
) -> tuple[float, float, bool, bool]:
    """Returns (lower, upper, lower_inclusive, upper_inclusive)."""
    INF = float("inf")
    if op == ">":
        return (t, INF, False, False)
    if op == ">=":
        return (t, INF, True, False)
    if op == "<":
        return (-INF, t, False, False)
    if op == "<=":
        return (-INF, t, False, True)
    # == is a degenerate point interval
    return (t, t, True, True)


def _intervals_overlap(
    lo1: float, hi1: float, li1: bool, hi1_inc: bool,
    lo2: float, hi2: float, li2: bool, hi2_inc: bool,
) -> bool:
    if lo1 > lo2:
        lo1, hi1, li1, hi1_inc, lo2, hi2, li2, hi2_inc = lo2, hi2, li2, hi2_inc, lo1, hi1, li1, hi1_inc
    if hi1 < lo2:
        return False
    if hi1 == lo2:
        return hi1_inc and li2
    return True


def _ast_to_text(node: ASTNode | str | float) -> str:
    if isinstance(node, str):
        return repr(node)
    if isinstance(node, (int, float)):
        return str(node)
    if node.op == "NOT":
        return f"NOT ({_ast_to_text(node.left)})"
    if node.right is None:
        return f"{node.op} {_ast_to_text(node.left)}"
    return f"({_ast_to_text(node.left)} {node.op} {_ast_to_text(node.right)})"


async def _llm_conflict_check(
    r1: RuleRecord, r2: RuleRecord, llm: LLMClient
) -> ConflictReport | None:
    logger.debug(
        "conflict_check_start",
        extra={
            "rule_ids": [r1.rule_id, r2.rule_id],
            "actions": [r1.action, r2.action],
        },
    )

    prompt = CONFLICT_CHECK_PROMPT.format(
        action1=r1.action,
        condition1=_ast_to_text(r1.condition),
        action2=r2.action,
        condition2=_ast_to_text(r2.condition),
    )
    try:
        raw = await llm.generate(prompt)
        logger.info(
            "conflict_check_llm_response_received",
            extra={
                "rule_ids": [r1.rule_id, r2.rule_id],
                "response_length": len(raw),
                "response_preview": raw[:500] if len(raw) > 500 else raw,
            },
        )
        # Try to extract JSON from markdown code blocks first
        json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', raw, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Fallback: try to find JSON object in the response
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                # Last resort: try parsing the entire response
                json_str = raw.strip()

        parsed = json.loads(json_str)
        logger.info(
            "conflict_check_parse_success",
            extra={
                "rule_ids": [r1.rule_id, r2.rule_id],
                "has_conflict": parsed.get("conflicts", False),
                "reason": parsed.get("reason", ""),
                "parsed_keys": list(parsed.keys()),
            },
        )
    except json.JSONDecodeError as exc:
        logger.warning(
            "conflict_check_parse_error",
            extra={
                "rule_ids": [r1.rule_id, r2.rule_id],
                "error": str(exc),
                "error_type": type(exc).__name__,
                "error_message": exc.msg,
                "error_line": exc.lineno,
                "error_column": exc.colno,
                "raw_response": raw,
                "json_attempt": json_str if 'json_str' in locals() else "N/A",
            },
        )
        return None
    except Exception as exc:
        logger.warning(
            "conflict_check_failed",
            extra={
                "rule_ids": [r1.rule_id, r2.rule_id],
                "error": str(exc),
                "error_type": type(exc).__name__,
                "error_details": getattr(exc, '__dict__', {}),
            },
        )
        return None

    if not parsed.get("conflicts"):
        logger.debug(
            "conflict_check_no_conflict",
            extra={"rule_ids": [r1.rule_id, r2.rule_id]},
        )
        return None

    logger.info(
        "conflict_check_conflict_found",
        extra={
            "rule_ids": [r1.rule_id, r2.rule_id],
            "reason": parsed.get("reason", ""),
        },
    )

    return ConflictReport(
        rule_ids=[r1.rule_id, r2.rule_id],
        overlap_description=parsed.get("reason", f"{r1.rule_id} conflicts with {r2.rule_id}"),
    )
