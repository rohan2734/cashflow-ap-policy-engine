from shared_types.pipeline import RawExtraction, ValidatedExtraction


VALID_OPS = {">", "<", ">=", "<=", "==", "AND", "OR", "NOT", "*", "+"}
VALID_ACTIONS = {"APPROVE", "ESCALATE", "REJECT"}


class ValidationError(Exception):
    pass


def validate_extraction(raw: RawExtraction) -> ValidatedExtraction:
    if not raw.condition_raw:
        raise ValidationError(f"Missing condition in {raw.clause_id!r}")
    if raw.action_raw not in VALID_ACTIONS:
        raise ValidationError(f"Invalid action {raw.action_raw!r} in {raw.clause_id!r}")
    _check_ops(raw.condition_raw, raw.clause_id)
    return ValidatedExtraction(
        clause_id=raw.clause_id,
        condition=raw.condition_raw,
        action=raw.action_raw,
        exceptions=raw.exceptions_raw,
        confidence=1.0,
    )


def _check_ops(node: dict, clause_id: str) -> None:
    op = node.get("op")
    if op and op not in VALID_OPS:
        raise ValidationError(f"Unknown op {op!r} in {clause_id!r}")
    for key in ("left", "right"):
        child = node.get(key)
        if isinstance(child, dict):
            _check_ops(child, clause_id)
