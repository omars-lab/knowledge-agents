"""
FastAPI server for the Claude Agent service.

Endpoints:
  GET  /health                      — Health check
  POST /api/v1/chat                 — Buffered chat (full response)
  POST /api/v1/chat/stream          — Streaming chat (SSE)
  GET  /api/v1/sessions             — List sessions
  DELETE /api/v1/sessions/{id}      — Close a session
  GET  /api/v1/sessions/{id}/artifacts — List session files
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
import subprocess
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel

from .agent import run_agent_buffered, stream_agent_response
from .config import ClaudeAgentSettings
from .tools import close_tool_clients, init_tool_clients

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prometheus metrics (claude_agent_ namespace, separate from agentic-api)
# ---------------------------------------------------------------------------

CHAT_REQUESTS = Counter(
    "claude_agent_chat_requests_total",
    "Total chat requests",
    ["status"],  # success, error, transport_error
)
CHAT_DURATION = Histogram(
    "claude_agent_chat_duration_seconds",
    "Chat response time in seconds",
    buckets=[1, 5, 10, 30, 60, 120, 300, 600],
)
TOOL_CALLS = Counter(
    "claude_agent_tool_calls_total",
    "Tool invocations by name",
    ["tool_name"],
)
RATE_LIMIT_EVENTS = Counter(
    "claude_agent_rate_limit_events_total",
    "Rate limit events by status",
    ["status"],  # allowed, allowed_warning, rejected
)
COST_TOTAL = Counter(
    "claude_agent_cost_usd_total",
    "Cumulative API cost in USD",
)
STREAM_REQUESTS = Counter(
    "claude_agent_stream_requests_total",
    "Total streaming chat requests",
    ["status"],
)

settings = ClaudeAgentSettings()


def _setup_logging() -> None:
    """Configure structured logging for the claude-agent service."""
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

    class _RequestIdFormatter(logging.Formatter):
        """Formatter that injects request_id with a safe default."""

        def format(self, record):
            if not hasattr(record, "request_id"):
                record.request_id = "-"
            return super().format(record)

    class _JsonFormatter(logging.Formatter):
        """JSON formatter for file handlers — structured for Loki ingestion."""

        def format(self, record):
            return json.dumps({
                "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "service": "claude-agent",
                "request_id": getattr(record, "request_id", None),
                "lineno": record.lineno,
            })

    console_fmt = _RequestIdFormatter(
        "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d [%(request_id)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    json_fmt = _JsonFormatter()

    # Console handler (plain text for humans)
    console = logging.StreamHandler()
    console.setFormatter(console_fmt)
    console.setLevel(log_level)

    # File handler (JSON for Loki/machine consumption)
    handlers = [console]
    logs_dir = Path("build/logs")
    if logs_dir.exists():
        file_handler = logging.handlers.RotatingFileHandler(
            logs_dir / "claude_agent.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        file_handler.setFormatter(json_fmt)
        file_handler.setLevel(log_level)
        handlers.append(file_handler)

    root = logging.getLogger()
    root.setLevel(log_level)
    root.handlers = handlers

    # Quiet noisy libraries
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def _check_claude_auth() -> None:
    """Check Claude CLI auth status at startup and log warnings if not authenticated."""
    try:
        result = subprocess.run(
            ["claude", "auth", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            auth_info = json.loads(result.stdout)
            if auth_info.get("loggedIn"):
                logger.info(
                    "Claude CLI authenticated — method=%s email=%s org=%s",
                    auth_info.get("authMethod", "?"),
                    auth_info.get("email", "?"),
                    auth_info.get("orgName", "?"),
                )
                # Check token file age for staleness warning
                token_file = Path.home() / ".claude" / ".claude.json"
                if token_file.exists():
                    age_hours = (time.time() - token_file.stat().st_mtime) / 3600
                    if age_hours > 168:  # 7 days
                        logger.warning(
                            "Claude auth token is %.0f hours old (%.1f days) — "
                            "consider refreshing: make claude-agent-login",
                            age_hours,
                            age_hours / 24,
                        )
                    else:
                        logger.info("Claude auth token age: %.1f hours", age_hours)
            else:
                logger.error(
                    "Claude CLI NOT authenticated — agent queries will fail. "
                    "Run: make claude-agent-login"
                )
        else:
            logger.error(
                "Claude CLI auth check failed (rc=%d) — stderr: %s",
                result.returncode,
                result.stderr.strip()[:200],
            )
    except FileNotFoundError:
        logger.error("Claude CLI not found — ensure @anthropic-ai/claude-code is installed")
    except subprocess.TimeoutExpired:
        logger.warning("Claude CLI auth check timed out after 15s")
    except Exception:
        logger.warning("Claude CLI auth check failed", exc_info=True)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and tear down shared resources."""
    _setup_logging()
    _check_claude_auth()
    logger.info("Initializing Claude Agent tool clients...")
    try:
        init_tool_clients(settings)
        stream_timeout = os.environ.get("CLAUDE_CODE_STREAM_CLOSE_TIMEOUT", "60000")
        logger.info(
            "Claude Agent service ready — qdrant=%s:%s neo4j=%s stream_close_timeout=%sms",
            settings.qdrant_host,
            settings.qdrant_port,
            settings.neo4j_uri,
            stream_timeout,
        )
    except Exception:
        logger.exception("FATAL: Failed to initialize tool clients")
        raise
    yield
    logger.info("Shutting down Claude Agent tool clients...")
    close_tool_clients()


app = FastAPI(
    title="Claude Agent API",
    description="Multi-turn conversational agent for notes and knowledge graphs",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    response: str
    tools_used: list[str]
    metadata: dict


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy", "service": "claude-agent"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message and get a full buffered response."""
    request_id = uuid.uuid4().hex[:8]
    log = logging.LoggerAdapter(logger, {"request_id": request_id})
    log.info(
        "chat request — session=%s message=%r",
        request.session_id or "(new)",
        request.message[:120],
    )
    start = time.monotonic()

    try:
        response_text, metadata = await run_agent_buffered(
            message=request.message,
            settings=settings,
            session_id=request.session_id,
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        log.info(
            "chat response — session=%s tools=%s duration=%dms cost=$%.4f response_len=%d",
            metadata.get("session_id", "?"),
            metadata.get("tools_used", []),
            elapsed_ms,
            metadata.get("cost_usd") or 0,
            len(response_text),
        )

        # Record Prometheus metrics
        CHAT_REQUESTS.labels(status="success").inc()
        CHAT_DURATION.observe((time.monotonic() - start))
        cost = metadata.get("cost_usd") or 0
        if cost:
            COST_TOTAL.inc(cost)
        for tool in metadata.get("tools_used", []):
            TOOL_CALLS.labels(tool_name=tool).inc()

        return ChatResponse(
            session_id=metadata.get("session_id", ""),
            response=response_text,
            tools_used=metadata.get("tools_used", []),
            metadata=metadata,
        )
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        log.exception("chat FAILED after %dms — session=%s", elapsed_ms, request.session_id)
        # Record error metric
        exc_name = type(exc).__name__
        if "CLIConnectionError" in exc_name or "ProcessTransport" in str(exc):
            CHAT_REQUESTS.labels(status="transport_error").inc()
        else:
            CHAT_REQUESTS.labels(status="error").inc()
        CHAT_DURATION.observe((time.monotonic() - start))
        # Surface CLIConnectionError as a 503 with actionable details
        if "CLIConnectionError" in exc_name or "ProcessTransport" in str(exc):
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "agent_transport_error",
                    "message": str(exc),
                    "duration_ms": elapsed_ms,
                    "hint": "The agent subprocess exited. Check auth (make claude-agent-auth-status) or increase max_turns.",
                },
            )
        raise


@app.post("/api/v1/chat/stream")
async def chat_stream(request: ChatRequest):
    """Send a message and get a Server-Sent Events stream."""
    request_id = uuid.uuid4().hex[:8]
    log = logging.LoggerAdapter(logger, {"request_id": request_id})
    log.info(
        "stream request — session=%s message=%r",
        request.session_id or "(new)",
        request.message[:120],
    )

    async def event_generator():
        start = time.monotonic()
        event_count = 0
        try:
            async for event in stream_agent_response(
                message=request.message,
                settings=settings,
                session_id=request.session_id,
            ):
                event_count += 1
                yield f"data: {json.dumps(event)}\n\n"
            elapsed_ms = int((time.monotonic() - start) * 1000)
            log.info("stream complete — %d events in %dms", event_count, elapsed_ms)
        except Exception:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            log.exception("stream FAILED after %dms (%d events)", elapsed_ms, event_count)
            yield f"data: {json.dumps({'type': 'error', 'message': 'Internal error'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(), media_type="text/event-stream"
    )


@app.get("/api/v1/sessions")
async def list_sessions():
    """List all session workspaces."""
    sessions_dir = Path("build/sessions")
    if not sessions_dir.exists():
        return {"sessions": []}

    sessions = []
    for session_dir in sorted(sessions_dir.iterdir()):
        meta_path = session_dir / "session.json"
        if meta_path.exists():
            with open(meta_path) as f:
                sessions.append(json.load(f))

    return {"sessions": sessions}


@app.delete("/api/v1/sessions/{session_id}")
async def delete_session(session_id: str):
    """Mark a session as closed."""
    meta_path = Path("build/sessions") / session_id / "session.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    with open(meta_path) as f:
        meta = json.load(f)
    meta["status"] = "closed"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    return {"status": "closed", "session_id": session_id}


@app.get("/api/v1/sessions/{session_id}/artifacts")
async def list_session_artifacts(session_id: str):
    """List all files in a session workspace."""
    session_dir = Path("build/sessions") / session_id
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    artifacts = []
    for path in sorted(session_dir.rglob("*")):
        if path.is_file():
            artifacts.append(str(path.relative_to(session_dir)))

    return {"session_id": session_id, "artifacts": artifacts}
