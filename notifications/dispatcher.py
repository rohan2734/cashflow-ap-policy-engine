import httpx
import logging
from shared_types.invoice import ExecutionResult
from config.types import NotificationConfig

logger = logging.getLogger(__name__)


async def dispatch(result: ExecutionResult, config: NotificationConfig) -> None:
    if not config.endpoint:
        return
    payload = {
        "invoice_id": result.invoice_id,
        "doc_id": result.doc_id,
        "decision": result.decision,
        "triggered_rule_ids": result.triggered_rule_ids,
        "reasons": result.reasons,
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(config.endpoint, json=payload, timeout=10.0)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning(
                "dispatch_failed",
                extra={"invoice_id": result.invoice_id, "error": str(exc)},
            )
