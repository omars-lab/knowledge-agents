"""
Langfuse tracing utility for LLM observability (v4 SDK).

Provides a thin wrapper around the Langfuse v4 SDK with graceful degradation.
If Langfuse is not configured or unreachable, all trace functions are no-ops.

Usage:
    from knowledge_agents.utils.langfuse_trace import get_langfuse

    langfuse = get_langfuse()
    if langfuse:
        with langfuse.start_as_current_observation(type="trace", name="chat", input=msg):
            with langfuse.start_as_current_observation(type="span", name="tool_call"):
                ...
            langfuse.update_current_generation(output=response)
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_client = None
_initialized = False


def get_langfuse():
    """Lazy-init Langfuse client. Returns None if not configured.

    Config via env vars:
        LANGFUSE_PUBLIC_KEY  (default: pk-lf-knowledge)
        LANGFUSE_SECRET_KEY  (default: sk-lf-knowledge)
        LANGFUSE_HOST        (default: http://localhost:3210)
        LANGFUSE_ENABLED     (default: true, set to 'false' to disable)
    """
    global _client, _initialized

    if _initialized:
        return _client

    _initialized = True

    if os.environ.get("LANGFUSE_ENABLED", "true").lower() == "false":
        logger.info("Langfuse disabled (LANGFUSE_ENABLED=false)")
        return None

    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "pk-lf-knowledge")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "sk-lf-knowledge")
    host = os.environ.get("LANGFUSE_HOST", "http://localhost:3210")

    try:
        from langfuse import Langfuse

        _client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
        _client.auth_check()
        logger.info("Langfuse connected at %s (v4 SDK)", host)
    except ImportError:
        logger.info("Langfuse SDK not installed — tracing disabled")
        _client = None
    except Exception as e:
        logger.warning("Langfuse connection failed (%s) — tracing disabled", e)
        _client = None

    return _client


def create_trace(name: str, **kwargs):
    """Create a trace observation. Returns a context manager or None.

    Usage:
        trace_ctx = create_trace("chat", input=msg)
        if trace_ctx:
            with trace_ctx:
                # ... do work ...
                pass
    """
    client = get_langfuse()
    if not client:
        return None
    try:
        return client.start_as_current_observation(
            name=name, as_type="span", **kwargs
        )
    except Exception as e:
        logger.debug("Failed to create Langfuse trace: %s", e)
        return None


def start_span(name: str, **kwargs):
    """Start a span within the current trace. Returns context manager or None."""
    client = get_langfuse()
    if not client:
        return None
    try:
        return client.start_as_current_observation(
            name=name, as_type="tool", **kwargs
        )
    except Exception as e:
        logger.debug("Failed to start Langfuse span: %s", e)
        return None


def start_generation(name: str, **kwargs):
    """Start a generation (LLM call) within current trace. Returns context manager or None."""
    client = get_langfuse()
    if not client:
        return None
    try:
        return client.start_as_current_observation(
            name=name, as_type="generation", **kwargs
        )
    except Exception as e:
        logger.debug("Failed to start Langfuse generation: %s", e)
        return None


def score_current(name: str, value: float, **kwargs):
    """Score the current trace."""
    client = get_langfuse()
    if not client:
        return
    try:
        client.score_current_trace(name=name, value=value, **kwargs)
    except Exception as e:
        logger.debug("Failed to score trace: %s", e)


def flush():
    """Flush pending traces to Langfuse. Call on shutdown."""
    if _client:
        try:
            _client.flush()
        except Exception:
            pass


def shutdown():
    """Shutdown Langfuse client. Call on app teardown."""
    global _client, _initialized
    flush()
    if _client:
        try:
            _client.shutdown()
        except Exception:
            pass
    _client = None
    _initialized = False
