"""
Unit tests for the Claude Agent system prompt.
"""
import pytest


@pytest.mark.unit
class TestSystemPrompt:
    """Tests for the system prompt content and structure."""

    def test_get_system_prompt_returns_string(self):
        """get_system_prompt should return a non-empty string."""
        from knowledge_agents.claude_agent.prompts import get_system_prompt

        prompt = get_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_prompt_mentions_all_tools(self):
        """System prompt should document all active tools."""
        from knowledge_agents.claude_agent.prompts import get_system_prompt

        prompt = get_system_prompt()
        # These are the currently active tools (semantic_search disabled until embeddings configured)
        tools = [
            "read_note",
            "build_knowledge_graph",
            "query_knowledge_graph",
            "derive_xcallback_url",
        ]
        for tool_name in tools:
            assert tool_name in prompt, f"Tool '{tool_name}' not found in system prompt"

    def test_prompt_has_workflow_sections(self):
        """System prompt should contain workflow guidance."""
        from knowledge_agents.claude_agent.prompts import get_system_prompt

        prompt = get_system_prompt()
        assert "Read and Explore" in prompt
        assert "Knowledge Graph Building" in prompt
        assert "Graph Exploration" in prompt

    def test_prompt_has_guidelines(self):
        """System prompt should contain behavioral guidelines."""
        from knowledge_agents.claude_agent.prompts import get_system_prompt

        prompt = get_system_prompt()
        assert "Guidelines" in prompt
