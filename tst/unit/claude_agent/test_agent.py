"""
Unit tests for Claude Agent session management and execution.

Uses mocked Claude Agent SDK — no real API calls.
"""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.unit
class TestBuildOptions:
    """Tests for _build_options helper."""

    @patch("knowledge_agents.claude_agent.agent.create_notes_mcp_server")
    def test_build_options_defaults(self, mock_mcp):
        """_build_options should create options with correct defaults."""
        from knowledge_agents.claude_agent.agent import _build_options
        from knowledge_agents.claude_agent.config import ClaudeAgentSettings

        mock_mcp.return_value = MagicMock()
        settings = ClaudeAgentSettings()

        options = _build_options(settings)

        assert options.system_prompt is not None
        assert options.include_partial_messages is True
        assert options.max_turns == 50
        assert options.resume is None
        # tools restricts agent to MCP tools only
        assert options.tools is not None
        assert len(options.tools) > 0

    @patch("knowledge_agents.claude_agent.agent.create_notes_mcp_server")
    def test_build_options_with_session_resume(self, mock_mcp):
        """_build_options should set resume when session_id is provided."""
        from knowledge_agents.claude_agent.agent import _build_options
        from knowledge_agents.claude_agent.config import ClaudeAgentSettings

        mock_mcp.return_value = MagicMock()
        settings = ClaudeAgentSettings()

        options = _build_options(settings, session_id="abc123")

        assert options.resume == "abc123"

    @patch("knowledge_agents.claude_agent.agent.create_notes_mcp_server")
    def test_build_options_with_custom_model(self, mock_mcp):
        """_build_options should set model when configured."""
        from knowledge_agents.claude_agent.agent import _build_options
        from knowledge_agents.claude_agent.config import ClaudeAgentSettings

        mock_mcp.return_value = MagicMock()
        settings = ClaudeAgentSettings(claude_model="claude-sonnet-4-6")

        options = _build_options(settings)

        assert options.model == "claude-sonnet-4-6"


@pytest.mark.unit
class TestSessionWorkspace:
    """Tests for session workspace management."""

    def test_ensure_session_workspace_creates_dirs(self, tmp_path, monkeypatch):
        """_ensure_session_workspace should create all subdirectories."""
        from knowledge_agents.claude_agent.agent import _ensure_session_workspace
        from knowledge_agents.claude_agent.config import ClaudeAgentSettings

        monkeypatch.chdir(tmp_path)
        settings = ClaudeAgentSettings()

        ws = _ensure_session_workspace(settings, "test-session-123")

        assert ws.exists()
        assert (ws / "turns").is_dir()
        assert (ws / "search_results").is_dir()
        assert (ws / "graphs").is_dir()
        assert (ws / "eval").is_dir()

    def test_write_session_metadata_new(self, tmp_path, monkeypatch):
        """_write_session_metadata should create session.json for new session."""
        from knowledge_agents.claude_agent.agent import _write_session_metadata

        session_dir = tmp_path / "test-session"
        session_dir.mkdir()

        _write_session_metadata(
            session_dir,
            "test-session",
            turns=1,
            total_cost_usd=0.05,
            model="claude-opus-4-6",
            queries=["What are my notes about AI?"],
            tools_used=["semantic_search"],
        )

        meta_path = session_dir / "session.json"
        assert meta_path.exists()

        with open(meta_path) as f:
            meta = json.load(f)

        assert meta["session_id"] == "test-session"
        assert meta["turns"] == 1
        assert meta["total_cost_usd"] == 0.05
        assert meta["status"] == "active"
        assert "created_at" in meta
        assert meta["queries"] == ["What are my notes about AI?"]
        assert meta["tools_used"] == ["semantic_search"]

    def test_write_session_metadata_update(self, tmp_path):
        """_write_session_metadata should update existing session.json."""
        from knowledge_agents.claude_agent.agent import _write_session_metadata

        session_dir = tmp_path / "test-session"
        session_dir.mkdir()

        # Create initial metadata
        _write_session_metadata(
            session_dir,
            "test-session",
            turns=1,
            tools_used=["semantic_search"],
        )

        # Update with turn 2
        _write_session_metadata(
            session_dir,
            "test-session",
            turns=2,
            total_cost_usd=0.10,
            queries=["Follow-up question"],
            tools_used=["read_note"],
        )

        with open(session_dir / "session.json") as f:
            meta = json.load(f)

        assert meta["turns"] == 2
        assert meta["total_cost_usd"] == 0.10
        assert "semantic_search" in meta["tools_used"]
        assert "read_note" in meta["tools_used"]

    def test_write_turn_artifacts(self, tmp_path):
        """_write_turn_artifacts should write prompt, response, and tools files."""
        from knowledge_agents.claude_agent.agent import _write_turn_artifacts

        session_dir = tmp_path / "test-session"
        turns_dir = session_dir / "turns"
        turns_dir.mkdir(parents=True)

        _write_turn_artifacts(
            session_dir,
            turn_number=1,
            prompt="What notes mention AI?",
            response_text="I found 3 notes about AI...",
            tool_calls=[
                {"name": "semantic_search", "input": '{"query": "AI"}'}
            ],
        )

        assert (turns_dir / "turn_001_prompt.md").read_text() == "What notes mention AI?"
        assert "3 notes" in (turns_dir / "turn_001_response.md").read_text()
        assert (turns_dir / "turn_001_tools.json").exists()


@pytest.mark.unit
class TestStreamAgentResponse:
    """Tests for stream_agent_response with mocked SDK."""

    @pytest.mark.asyncio
    @patch("knowledge_agents.claude_agent.agent.query")
    @patch("knowledge_agents.claude_agent.agent.create_notes_mcp_server")
    async def test_stream_text_events(self, mock_mcp, mock_query, tmp_path, monkeypatch):
        """stream_agent_response should yield text events from StreamEvent."""
        from claude_agent_sdk.types import ResultMessage, StreamEvent

        from knowledge_agents.claude_agent.agent import stream_agent_response
        from knowledge_agents.claude_agent.config import ClaudeAgentSettings

        monkeypatch.chdir(tmp_path)
        mock_mcp.return_value = MagicMock()

        # Simulate SDK yielding a text delta then a result
        text_event = StreamEvent(
            uuid="1",
            session_id="sess-1",
            event={
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": "Hello world"},
            },
        )
        result_msg = ResultMessage(
            subtype="result",
            duration_ms=100,
            duration_api_ms=80,
            is_error=False,
            num_turns=1,
            session_id="sess-1",
            total_cost_usd=0.01,
        )

        async def mock_query_fn(**kwargs):
            yield text_event
            yield result_msg

        mock_query.side_effect = mock_query_fn

        settings = ClaudeAgentSettings()
        events = []
        async for event in stream_agent_response("test", settings):
            events.append(event)

        text_events = [e for e in events if e["type"] == "text"]
        result_events = [e for e in events if e["type"] == "result"]

        assert len(text_events) == 1
        assert text_events[0]["content"] == "Hello world"
        assert len(result_events) == 1
        assert result_events[0]["session_id"] == "sess-1"

    @pytest.mark.asyncio
    @patch("knowledge_agents.claude_agent.agent.query")
    @patch("knowledge_agents.claude_agent.agent.create_notes_mcp_server")
    async def test_stream_tool_events(self, mock_mcp, mock_query, tmp_path, monkeypatch):
        """stream_agent_response should yield tool start/input/complete events."""
        from claude_agent_sdk.types import ResultMessage, StreamEvent

        from knowledge_agents.claude_agent.agent import stream_agent_response
        from knowledge_agents.claude_agent.config import ClaudeAgentSettings

        monkeypatch.chdir(tmp_path)
        mock_mcp.return_value = MagicMock()

        events_from_sdk = [
            StreamEvent(
                uuid="1",
                session_id="sess-1",
                event={
                    "type": "content_block_start",
                    "content_block": {"type": "tool_use", "name": "semantic_search"},
                },
            ),
            StreamEvent(
                uuid="2",
                session_id="sess-1",
                event={
                    "type": "content_block_delta",
                    "delta": {
                        "type": "input_json_delta",
                        "partial_json": '{"query": "AI"}',
                    },
                },
            ),
            StreamEvent(
                uuid="3",
                session_id="sess-1",
                event={"type": "content_block_stop"},
            ),
            ResultMessage(
                subtype="result",
                duration_ms=200,
                duration_api_ms=150,
                is_error=False,
                num_turns=1,
                session_id="sess-1",
                total_cost_usd=0.02,
            ),
        ]

        async def mock_query_fn(**kwargs):
            for e in events_from_sdk:
                yield e

        mock_query.side_effect = mock_query_fn

        settings = ClaudeAgentSettings()
        events = []
        async for event in stream_agent_response("search AI", settings):
            events.append(event)

        types = [e["type"] for e in events]
        assert "tool_start" in types
        assert "tool_input" in types
        assert "tool_complete" in types
        assert "result" in types


@pytest.mark.unit
class TestRunAgentBuffered:
    """Tests for run_agent_buffered."""

    @pytest.mark.asyncio
    @patch("knowledge_agents.claude_agent.agent.stream_agent_response")
    async def test_buffered_collects_text(self, mock_stream):
        """run_agent_buffered should collect all text and return metadata."""
        from knowledge_agents.claude_agent.agent import run_agent_buffered
        from knowledge_agents.claude_agent.config import ClaudeAgentSettings

        async def mock_events(*args, **kwargs):
            yield {"type": "tool_start", "name": "semantic_search"}
            yield {"type": "text", "content": "Found "}
            yield {"type": "text", "content": "3 notes."}
            yield {
                "type": "result",
                "session_id": "sess-1",
                "cost_usd": 0.05,
                "turns": 1,
                "duration_ms": 500,
            }

        mock_stream.return_value = mock_events()

        settings = ClaudeAgentSettings()
        text, metadata = await run_agent_buffered("test", settings)

        assert text == "Found 3 notes."
        assert metadata["session_id"] == "sess-1"
        assert metadata["cost_usd"] == 0.05
        assert "semantic_search" in metadata["tools_used"]
