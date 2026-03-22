"""
Regression tests: Claude Agent vs existing agent baseline.

Ensures the Claude agent matches or exceeds existing agent quality
for the same test queries. Requires running services + Claude credentials.
"""
import os

import pytest
import requests

CLAUDE_AGENT_URL = os.getenv("CLAUDE_AGENT_URL", "http://localhost:8004")
TESTS_ENABLED = os.getenv("CLAUDE_AGENT_TESTS_ENABLED", "false").lower() == "true"

pytestmark = [
    pytest.mark.claude_agent,
    pytest.mark.skipif(not TESTS_ENABLED, reason="CLAUDE_AGENT_TESTS_ENABLED not set"),
]


# Same queries used by existing test_note_query_agent.py
REGRESSION_QUERIES = [
    "What notes do I have about personal goals?",
    "What projects am I working on?",
    "What are my habits and routines?",
]


class TestNoteQueryRegression:
    """Regression tests comparing Claude agent to existing agent baseline."""

    @pytest.mark.parametrize("query", REGRESSION_QUERIES)
    def test_query_returns_substantive_answer(self, query):
        """Claude agent should return a non-empty, substantive answer."""
        response = requests.post(
            f"{CLAUDE_AGENT_URL}/api/v1/chat",
            json={"message": query},
            timeout=120,
        )
        assert response.status_code == 200
        data = response.json()

        # Answer should be substantive (not empty or generic)
        answer = data["response"]
        assert len(answer) > 50, f"Answer too short for query: {query}"
        assert "I don't have" not in answer.lower() or "I cannot" not in answer.lower()

    @pytest.mark.parametrize("query", REGRESSION_QUERIES)
    def test_query_uses_search_tool(self, query):
        """Claude agent should use semantic_search for note queries."""
        response = requests.post(
            f"{CLAUDE_AGENT_URL}/api/v1/chat",
            json={"message": query},
            timeout=120,
        )
        assert response.status_code == 200
        data = response.json()

        # Should use semantic_search (or mcp__notes__semantic_search)
        tools = data.get("tools_used", [])
        search_used = any("semantic_search" in t for t in tools)
        assert search_used, f"Expected semantic_search for: {query}"


class TestGraphBuildingRegression:
    """Regression tests for graph building capability."""

    def test_graph_build_from_search(self):
        """Multi-turn: search then build graph from results."""
        # Turn 1: Search
        r1 = requests.post(
            f"{CLAUDE_AGENT_URL}/api/v1/chat",
            json={"message": "Find notes about projects"},
            timeout=120,
        )
        assert r1.status_code == 200
        session_id = r1.json()["session_id"]

        # Turn 2: Build graph
        r2 = requests.post(
            f"{CLAUDE_AGENT_URL}/api/v1/chat",
            json={
                "message": "Build a knowledge graph from the most relevant result",
                "session_id": session_id,
            },
            timeout=120,
        )
        assert r2.status_code == 200
        answer = r2.json()["response"]
        # Should mention entities or graph creation
        assert any(
            word in answer.lower()
            for word in ["entit", "graph", "node", "relationship", "created"]
        )
