"""
Integration tests for Claude Agent API endpoints.

Requires running services: Qdrant, Neo4j, tidy-mcp, llm-proxy + Claude credentials.
Skip unless CLAUDE_AGENT_TESTS_ENABLED=true.
"""
import json
import os

import pytest
import requests

CLAUDE_AGENT_URL = os.getenv("CLAUDE_AGENT_URL", "http://localhost:8004")
TESTS_ENABLED = os.getenv("CLAUDE_AGENT_TESTS_ENABLED", "false").lower() == "true"

pytestmark = [
    pytest.mark.claude_agent,
    pytest.mark.skipif(not TESTS_ENABLED, reason="CLAUDE_AGENT_TESTS_ENABLED not set"),
]


class TestHealthEndpoint:
    """Integration tests for the health endpoint."""

    def test_health_returns_healthy(self):
        """Health endpoint should return 200 with healthy status."""
        response = requests.get(f"{CLAUDE_AGENT_URL}/health", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestBufferedChatEndpoint:
    """Integration tests for the /api/v1/chat endpoint."""

    def test_chat_returns_valid_response(self):
        """Chat should return a response with session_id."""
        response = requests.post(
            f"{CLAUDE_AGENT_URL}/api/v1/chat",
            json={"message": "What notes do I have about projects?"},
            timeout=120,
        )
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert len(data["response"]) > 0
        assert isinstance(data["tools_used"], list)

    def test_multi_turn_maintains_context(self):
        """Turn 2 should reuse session_id and maintain context."""
        # Turn 1
        r1 = requests.post(
            f"{CLAUDE_AGENT_URL}/api/v1/chat",
            json={"message": "Find my notes about goals"},
            timeout=120,
        )
        assert r1.status_code == 200
        session_id = r1.json()["session_id"]
        assert session_id

        # Turn 2 — same session
        r2 = requests.post(
            f"{CLAUDE_AGENT_URL}/api/v1/chat",
            json={
                "message": "Can you summarize those results?",
                "session_id": session_id,
            },
            timeout=120,
        )
        assert r2.status_code == 200


class TestStreamingChatEndpoint:
    """Integration tests for the /api/v1/chat/stream endpoint."""

    def test_stream_produces_sse_events(self):
        """Stream endpoint should produce valid SSE ending with [DONE]."""
        response = requests.post(
            f"{CLAUDE_AGENT_URL}/api/v1/chat/stream",
            json={"message": "Search for notes about habits"},
            timeout=120,
            stream=True,
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        events = []
        for line in response.iter_lines(decode_unicode=True):
            if line and line.startswith("data: "):
                payload = line[6:]
                if payload == "[DONE]":
                    break
                events.append(json.loads(payload))

        # Should have at least one result event
        event_types = {e.get("type") for e in events}
        assert "result" in event_types


class TestSessionEndpoints:
    """Integration tests for session management."""

    def test_list_sessions(self):
        """Sessions endpoint should return a list."""
        response = requests.get(
            f"{CLAUDE_AGENT_URL}/api/v1/sessions", timeout=10
        )
        assert response.status_code == 200
        assert "sessions" in response.json()
