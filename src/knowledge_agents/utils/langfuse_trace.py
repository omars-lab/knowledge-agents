"""
Langfuse tracing utility for LLM observability.

Provides a thin wrapper around the Langfuse SDK with graceful degradation.
If Langfuse is not configured or unreachable, all trace functions are no-ops.

Usage:
    from knowledge_agents.utils.langfuse_trace import get_langfuse

    langfuse = get_langfuse()
    if langfuse:
        trace = langfuse.trace(name="chat", input=message)
        trace.generation(name="llm_call", model=model, input=prompt, output=response)
        trace.update(output=final_response)
"""
from __future__ import annotations

import logging
import os
from typing import Any

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
        # Quick connectivity check
        _client.auth_check()
        logger.info("Langfuse connected at %s", host)
    except ImportError:
        logger.info("Langfuse SDK not installed — tracing disabled")
        _client = None
    except Exception as e:
        logger.warning("Langfuse connection failed (%s) — tracing disabled", e)
        _client = None

    return _client


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
