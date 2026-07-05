"""Lightweight runtime tracing for bottleneck analysis."""

import os
import sys
import time
from datetime import datetime
from typing import Any

TRACE_ENV_VAR = "TRADINGAGENTS_TIMING_LOGS"
_TRUTHY_VALUES = {"1", "true", "yes", "on"}


def runtime_trace_enabled() -> bool:
    """Return True when runtime timing traces should be emitted."""
    value = os.getenv(TRACE_ENV_VAR, "")
    return value.strip().lower() in _TRUTHY_VALUES


def format_elapsed(seconds: float) -> str:
    """Format elapsed seconds for trace output."""
    return f"{seconds:.2f}s"


def _compact(value: Any) -> str:
    text = " ".join(str(value).split())
    if len(text) > 160:
        return text[:157] + "..."
    return text


def emit_runtime_trace(event: str, **fields: Any) -> None:
    """Emit a compact trace line to stderr when tracing is enabled."""
    if not runtime_trace_enabled():
        return

    timestamp = datetime.now().strftime("%H:%M:%S")
    parts = [f"{key}={_compact(value)}" for key, value in fields.items() if value is not None]
    line = f"[{timestamp}] [TradingAgentsTrace] {event}"
    if parts:
        line += " | " + " ".join(parts)
    print(line, file=sys.stderr, flush=True)


def estimate_prompt_chars(payload: Any) -> int:
    """Estimate payload size without serializing the exact CLI prompt."""
    if isinstance(payload, str):
        return len(payload)

    if isinstance(payload, list):
        total = 0
        for item in payload:
            if hasattr(item, "content"):
                total += len(str(item.content))
            elif isinstance(item, dict):
                total += len(str(item.get("content", "")))
            elif isinstance(item, tuple) and len(item) == 2:
                total += len(str(item[1]))
            else:
                total += len(str(item))
        return total

    return len(str(payload))


def llm_label(llm: Any) -> str:
    """Return a short human-readable model label for tracing."""
    for attr in ("cli_model", "model_name", "model"):
        value = getattr(llm, attr, None)
        if value:
            return str(value)

    params = getattr(llm, "_identifying_params", None)
    if isinstance(params, dict):
        for key in ("cli_model", "model_name", "model"):
            value = params.get(key)
            if value:
                return str(value)

    return llm.__class__.__name__


def response_chars(response: Any) -> int:
    """Best-effort response size for trace output."""
    content = getattr(response, "content", None)
    if content is None:
        return len(str(response))
    return len(str(content))


def invoke_with_trace(node_name: str, llm: Any, payload: Any) -> Any:
    """Call llm.invoke() with step-level timing traces."""
    model = llm_label(llm)
    prompt_chars = estimate_prompt_chars(payload)
    emit_runtime_trace(
        "step.start",
        node=node_name,
        step="llm_invoke",
        model=model,
        prompt_chars=prompt_chars,
    )
    started = time.perf_counter()
    try:
        response = llm.invoke(payload)
    except Exception as exc:
        emit_runtime_trace(
            "step.fail",
            node=node_name,
            step="llm_invoke",
            model=model,
            elapsed=format_elapsed(time.perf_counter() - started),
            error=f"{type(exc).__name__}: {exc}",
        )
        raise
    emit_runtime_trace(
        "step.end",
        node=node_name,
        step="llm_invoke",
        model=model,
        elapsed=format_elapsed(time.perf_counter() - started),
        response_chars=response_chars(response),
    )
    return response
