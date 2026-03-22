"""
Unit tests for Claude Agent FastAPI server.

Tests endpoint schemas, health checks, and SSE format.
"""
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_returns_200(self):
        """Health endpoint should return healthy status."""
        from knowledge_agents.claude_agent.server import app

        # Patch lifespan to avoid initializing real clients
        with patch(
            "knowledge_agents.claude_agent.server.init_tool_clients"
        ), patch("knowledge_agents.claude_agent.server.close_tool_clients"):
            client = TestClient(app)
            response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "claude-agent"


@pytest.mark.unit
class TestChatEndpoint:
    """Tests for the /api/v1/chat endpoint."""

    def test_chat_validates_request_body(self):
        """Chat endpoint should reject invalid request bodies."""
        from knowledge_agents.claude_agent.server import app

        with patch(
            "knowledge_agents.claude_agent.server.init_tool_clients"
        ), patch("knowledge_agents.claude_agent.server.close_tool_clients"):
            client = TestClient(app)

            # Missing required 'message' field
            response = client.post("/api/v1/chat", json={})
            assert response.status_code == 422

    @patch("knowledge_agents.claude_agent.server.run_agent_buffered")
    def test_chat_returns_response(self, mock_agent):
        """Chat endpoint should return structured response."""
        from knowledge_agents.claude_agent.server import app

        mock_agent.return_value = (
            "Found 3 notes about AI",
            {
                "session_id": "sess-123",
                "cost_usd": 0.05,
                "turns": 1,
                "duration_ms": 500,
                "tools_used": ["semantic_search"],
            },
        )

        with patch(
            "knowledge_agents.claude_agent.server.init_tool_clients"
        ), patch("knowledge_agents.claude_agent.server.close_tool_clients"):
            client = TestClient(app)
            response = client.post(
                "/api/v1/chat",
                json={"message": "What notes do I have about AI?"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "sess-123"
        assert data["response"] == "Found 3 notes about AI"
        assert "semantic_search" in data["tools_used"]

    @patch("knowledge_agents.claude_agent.server.run_agent_buffered")
    def test_chat_with_session_id(self, mock_agent):
        """Chat endpoint should pass session_id for multi-turn."""
        from knowledge_agents.claude_agent.server import app

        mock_agent.return_value = ("Response", {"session_id": "sess-123", "tools_used": []})

        with patch(
            "knowledge_agents.claude_agent.server.init_tool_clients"
        ), patch("knowledge_agents.claude_agent.server.close_tool_clients"):
            client = TestClient(app)
            response = client.post(
                "/api/v1/chat",
                json={
                    "message": "Follow up question",
                    "session_id": "sess-123",
                },
            )

        assert response.status_code == 200
        mock_agent.assert_called_once()
        call_kwargs = mock_agent.call_args
        assert call_kwargs.kwargs.get("session_id") == "sess-123" or call_kwargs[1].get("session_id") == "sess-123"


@pytest.mark.unit
class TestStreamEndpoint:
    """Tests for the /api/v1/chat/stream endpoint."""

    @patch("knowledge_agents.claude_agent.server.stream_agent_response")
    def test_stream_returns_sse(self, mock_stream):
        """Stream endpoint should return text/event-stream."""
        from knowledge_agents.claude_agent.server import app

        async def mock_events(*args, **kwargs):
            yield {"type": "text", "content": "Hello"}
            yield {"type": "result", "session_id": "sess-1", "cost_usd": 0.01, "turns": 1}

        mock_stream.return_value = mock_events()

        with patch(
            "knowledge_agents.claude_agent.server.init_tool_clients"
        ), patch("knowledge_agents.claude_agent.server.close_tool_clients"):
            client = TestClient(app)
            response = client.post(
                "/api/v1/chat/stream",
                json={"message": "Hello"},
            )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        # Parse SSE events
        lines = response.text.strip().split("\n\n")
        events = []
        for line in lines:
            if line.startswith("data: ") and line != "data: [DONE]":
                events.append(json.loads(line[6:]))

        assert any(e.get("type") == "text" for e in events)


@pytest.mark.unit
class TestSessionEndpoints:
    """Tests for session management endpoints."""

    def test_list_sessions_empty(self, tmp_path, monkeypatch):
        """Sessions endpoint should return empty list when no sessions exist."""
        from knowledge_agents.claude_agent.server import app

        monkeypatch.chdir(tmp_path)

        with patch(
            "knowledge_agents.claude_agent.server.init_tool_clients"
        ), patch("knowledge_agents.claude_agent.server.close_tool_clients"):
            client = TestClient(app)
            response = client.get("/api/v1/sessions")

        assert response.status_code == 200
        assert response.json()["sessions"] == []

    def test_delete_session_not_found(self, tmp_path, monkeypatch):
        """Delete session should return 404 for nonexistent session."""
        from knowledge_agents.claude_agent.server import app

        monkeypatch.chdir(tmp_path)

        with patch(
            "knowledge_agents.claude_agent.server.init_tool_clients"
        ), patch("knowledge_agents.claude_agent.server.close_tool_clients"):
            client = TestClient(app)
            response = client.delete("/api/v1/sessions/nonexistent")

        assert response.status_code == 404

    def test_list_session_artifacts_not_found(self, tmp_path, monkeypatch):
        """Artifacts endpoint should return 404 for nonexistent session."""
        from knowledge_agents.claude_agent.server import app

        monkeypatch.chdir(tmp_path)

        with patch(
            "knowledge_agents.claude_agent.server.init_tool_clients"
        ), patch("knowledge_agents.claude_agent.server.close_tool_clients"):
            client = TestClient(app)
            response = client.get("/api/v1/sessions/nonexistent/artifacts")

        assert response.status_code == 404
