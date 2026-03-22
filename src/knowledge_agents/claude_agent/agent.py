"""
Claude Agent SDK integration with session management and workspace support.

Provides streaming and buffered agent execution using query() with
in-process MCP tools for note search, graph building, and exploration.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator

from claude_agent_sdk import ClaudeAgentOptions, query
from claude_agent_sdk.types import (
    AssistantMessage,
    RateLimitEvent,
    ResultMessage,
    StreamEvent,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)

from .config import ClaudeAgentSettings
from .prompts import get_system_prompt
from .tools import TOOL_NAMES, create_notes_mcp_server

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Session workspace helpers
# ---------------------------------------------------------------------------

def _session_dir(settings: ClaudeAgentSettings, session_id: str) -> Path:
    """Return the workspace directory for a session."""
    return Path("build/sessions") / session_id


def _ensure_session_workspace(settings: ClaudeAgentSettings, session_id: str) -> Path:
    """Create session workspace directories if they don't exist."""
    base = _session_dir(settings, session_id)
    for sub in ("turns", "search_results", "graphs", "eval"):
        (base / sub).mkdir(parents=True, exist_ok=True)
    return base


def _write_session_metadata(
    session_dir: Path,
    session_id: str,
    *,
    turns: int = 0,
    total_cost_usd: float = 0.0,
    model: str | None = None,
    queries: list[str] | None = None,
    tools_used: list[str] | None = None,
    status: str = "active",
) -> None:
    """Write or update session.json metadata file."""
    meta_path = session_dir / "session.json"

    now = datetime.now(timezone.utc).isoformat()
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)
        meta["updated_at"] = now
        meta["turns"] = turns
        meta["total_cost_usd"] = total_cost_usd
        meta["status"] = status
        if queries:
            meta["queries"] = queries
        if tools_used:
            meta["tools_used"] = list(set(meta.get("tools_used", []) + tools_used))
    else:
        meta = {
            "session_id": session_id,
            "created_at": now,
            "updated_at": now,
            "status": status,
            "turns": turns,
            "total_cost_usd": total_cost_usd,
            "model": model,
            "queries": queries or [],
            "tools_used": tools_used or [],
        }

    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)


def _write_turn_artifacts(
    session_dir: Path,
    turn_number: int,
    prompt: str,
    response_text: str,
    tool_calls: list[dict],
) -> None:
    """Write turn-level artifacts to the session workspace."""
    turns_dir = session_dir / "turns"
    prefix = f"turn_{turn_number:03d}"

    (turns_dir / f"{prefix}_prompt.md").write_text(prompt, encoding="utf-8")
    (turns_dir / f"{prefix}_response.md").write_text(response_text, encoding="utf-8")

    if tool_calls:
        with open(turns_dir / f"{prefix}_tools.json", "w") as f:
            json.dump(tool_calls, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# Agent execution
# ---------------------------------------------------------------------------

def _stderr_handler(line: str) -> None:
    """Log stderr output from the Claude CLI subprocess."""
    stripped = line.strip()
    if stripped:
        logger.debug("claude-cli stderr: %s", stripped)


def _build_options(
    settings: ClaudeAgentSettings,
    session_id: str | None = None,
) -> ClaudeAgentOptions:
    """Build ClaudeAgentOptions with MCP tools and optional session resume."""
    mcp_server = create_notes_mcp_server()

    opts = ClaudeAgentOptions(
        system_prompt=get_system_prompt(),
        mcp_servers={"notes": mcp_server},
        tools=TOOL_NAMES,
        allowed_tools=TOOL_NAMES,
        include_partial_messages=True,
        max_turns=settings.max_turns,
        permission_mode="bypassPermissions",
        stderr=_stderr_handler,
    )

    if settings.claude_model:
        opts.model = settings.claude_model

    if session_id:
        opts.resume = session_id

    logger.info(
        "built agent options — model=%s max_turns=%d session=%s tools=%d",
        settings.claude_model or "(default)",
        settings.max_turns,
        session_id or "(new)",
        len(TOOL_NAMES),
    )
    return opts


async def stream_agent_response(
    message: str,
    settings: ClaudeAgentSettings,
    session_id: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Stream agent response as typed SSE events.

    Yields dicts:
      {"type": "tool_start", "name": "semantic_search"}
      {"type": "tool_input", "chunk": '{"query": "AI notes"...'}
      {"type": "tool_complete", "name": "semantic_search", "input": "..."}
      {"type": "text", "content": "Based on your notes..."}
      {"type": "result", "session_id": "abc", "cost_usd": 0.05, "turns": 3}
    """
    options = _build_options(settings, session_id)

    current_tool: str | None = None
    tool_input = ""
    collected_text = ""
    tool_calls: list[dict] = []
    start = time.monotonic()
    msg_count = 0

    logger.info("stream_agent_response starting — message=%r", message[:120])

    try:
        async for msg in query(prompt=message, options=options):
            msg_count += 1

            if isinstance(msg, StreamEvent):
                event = msg.event
                event_type = event.get("type")

                if event_type == "content_block_start":
                    block = event.get("content_block", {})
                    if block.get("type") == "tool_use":
                        current_tool = block.get("name")
                        tool_input = ""
                        logger.debug("tool_start: %s", current_tool)
                        yield {"type": "tool_start", "name": current_tool}

                elif event_type == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "input_json_delta":
                        chunk = delta.get("partial_json", "")
                        tool_input += chunk
                        yield {"type": "tool_input", "chunk": chunk}
                    elif delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        collected_text += text
                        yield {"type": "text", "content": text}

                elif event_type == "content_block_stop":
                    if current_tool:
                        tool_calls.append(
                            {"name": current_tool, "input": tool_input}
                        )
                        logger.info(
                            "tool_complete: %s input_len=%d",
                            current_tool,
                            len(tool_input),
                        )
                        yield {
                            "type": "tool_complete",
                            "name": current_tool,
                            "input": tool_input,
                        }
                        current_tool = None

            elif isinstance(msg, AssistantMessage):
                # Complete message — extract any text blocks we may have missed
                for block in msg.content:
                    if isinstance(block, TextBlock) and block.text not in collected_text:
                        collected_text += block.text
                        yield {"type": "text", "content": block.text}

            elif isinstance(msg, ResultMessage):
                elapsed_ms = int((time.monotonic() - start) * 1000)
                result_session_id = msg.session_id
                logger.info(
                    "agent result — session=%s turns=%s cost=$%.4f sdk_events=%d elapsed=%dms",
                    result_session_id,
                    msg.num_turns,
                    msg.total_cost_usd or 0,
                    msg_count,
                    elapsed_ms,
                )

                # Write session workspace artifacts
                try:
                    ws = _ensure_session_workspace(settings, result_session_id)
                    _write_session_metadata(
                        ws,
                        result_session_id,
                        turns=msg.num_turns,
                        total_cost_usd=msg.total_cost_usd or 0.0,
                        model=settings.claude_model,
                        queries=[message],
                        tools_used=[tc["name"] for tc in tool_calls],
                    )
                    _write_turn_artifacts(
                        ws, msg.num_turns, message, collected_text, tool_calls
                    )
                except Exception:
                    logger.warning(
                        "Failed to write session workspace for %s",
                        result_session_id,
                        exc_info=True,
                    )

                yield {
                    "type": "result",
                    "session_id": result_session_id,
                    "cost_usd": msg.total_cost_usd,
                    "turns": msg.num_turns,
                    "duration_ms": msg.duration_ms,
                }

            elif isinstance(msg, RateLimitEvent):
                info = msg.rate_limit_info
                elapsed_ms = int((time.monotonic() - start) * 1000)
                if info.status == "rejected":
                    logger.warning(
                        "RATE LIMITED (rejected) — utilization=%.0f%% resets_at=%s type=%s elapsed=%dms",
                        (info.utilization or 0) * 100,
                        info.resets_at,
                        info.rate_limit_type,
                        elapsed_ms,
                    )
                elif info.status == "allowed_warning":
                    logger.info(
                        "rate limit warning — utilization=%.0f%% type=%s elapsed=%dms",
                        (info.utilization or 0) * 100,
                        info.rate_limit_type,
                        elapsed_ms,
                    )
                else:
                    logger.debug(
                        "rate limit allowed — utilization=%.0f%% type=%s",
                        (info.utilization or 0) * 100,
                        info.rate_limit_type,
                    )
                yield {
                    "type": "rate_limit",
                    "status": info.status,
                    "utilization": info.utilization,
                    "rate_limit_type": info.rate_limit_type,
                    "resets_at": info.resets_at,
                }

    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.error(
            "stream_agent_response FAILED after %dms (%d sdk events) — %s: %s",
            elapsed_ms,
            msg_count,
            type(exc).__name__,
            exc,
            exc_info=True,
        )
        raise


async def run_agent_buffered(
    message: str,
    settings: ClaudeAgentSettings,
    session_id: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Non-streaming variant — collects full response, returns (text, metadata)."""
    collected_text = ""
    metadata: dict[str, Any] = {}
    tools_used: list[str] = []

    async for event in stream_agent_response(message, settings, session_id):
        if event["type"] == "text":
            collected_text += event["content"]
        elif event["type"] == "tool_start":
            tools_used.append(event["name"])
        elif event["type"] == "result":
            metadata = {
                "session_id": event["session_id"],
                "cost_usd": event.get("cost_usd"),
                "turns": event.get("turns"),
                "duration_ms": event.get("duration_ms"),
                "tools_used": tools_used,
            }

    return collected_text, metadata
