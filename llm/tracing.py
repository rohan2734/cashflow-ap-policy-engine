import os
from contextvars import ContextVar
from typing import Any

from langfuse import Langfuse, observe

_trace_ctx: ContextVar[dict[str, Any]] = ContextVar("langfuse_trace_ctx", default={})


def get_langfuse() -> Langfuse:
    """Get or create Langfuse singleton instance."""
    if not hasattr(get_langfuse, "_instance"):
        public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
        secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "")
        host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")

        if not public_key or not secret_key:
            raise RuntimeError(
                "LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set in environment"
            )

        get_langfuse._instance = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
    return get_langfuse._instance


def set_trace_context(**kwargs: Any) -> None:
    """Set trace context for current async context."""
    current = _trace_ctx.get({})
    _trace_ctx.set({**current, **kwargs})


def get_trace_context() -> dict[str, Any]:
    """Get current trace context."""
    return _trace_ctx.get({})


def flush() -> None:
    """Flush pending Langfuse events."""
    if hasattr(get_langfuse, "_instance"):
        get_langfuse._instance.flush()
