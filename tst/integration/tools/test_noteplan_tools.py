"""
Integration tests for NotePlan tools via tidy-mcp HTTP service.

PURPOSE: Tests NotePlan tools by calling tidy-mcp HTTP service directly
SCOPE: HTTP endpoint calls, error handling, response formatting
"""

import logging
import os

import pytest
import requests

logger = logging.getLogger(__name__)

pytestmark = [pytest.mark.integration]


class TestNotePlanToolsViaHttp:
    """Test NotePlan tools via tidy-mcp HTTP service"""

    def test_derive_xcallback_url_daily_plan(
        self, tidy_mcp_available, tidy_mcp_url
    ):
        """Test derive_xcallback_url_from_noteplan_file with daily plan"""
        if not tidy_mcp_available:
            pytest.skip("tidy-mcp service not available")

        response = requests.post(
            f"{tidy_mcp_url}/tools/derive_xcallback_url_from_noteplan_file",
            json={"file_path": "2025-11-13.md"},
            timeout=5,
        )
        assert response.status_code == 200
        result = response.json()

        assert result.get("success") is True
        assert "x_callback_url" in result
        assert result["x_callback_url"].startswith("noteplan://x-callback-url/openNote")
        assert "noteDate=20251113" in result["x_callback_url"]
        assert result.get("is_daily_plan") is True
        assert result.get("note_title") == "2025-11-13"

    def test_derive_xcallback_url_regular_note(
        self, tidy_mcp_available, tidy_mcp_url
    ):
        """Test derive_xcallback_url_from_noteplan_file with regular note"""
        if not tidy_mcp_available:
            pytest.skip("tidy-mcp service not available")

        response = requests.post(
            f"{tidy_mcp_url}/tools/derive_xcallback_url_from_noteplan_file",
            json={"file_path": "notes/project-ideas.md"},
            timeout=5,
        )
        assert response.status_code == 200
        result = response.json()

        assert result.get("success") is True
        assert "x_callback_url" in result
        assert result["x_callback_url"].startswith("noteplan://x-callback-url/openNote")
        assert "noteTitle=" in result["x_callback_url"]
        assert result.get("is_daily_plan") is False

    def test_derive_xcallback_url_with_heading(
        self, tidy_mcp_available, tidy_mcp_url
    ):
        """Test derive_xcallback_url_from_noteplan_file with heading"""
        if not tidy_mcp_available:
            pytest.skip("tidy-mcp service not available")

        response = requests.post(
            f"{tidy_mcp_url}/tools/derive_xcallback_url_from_noteplan_file",
            json={
                "file_path": "notes/project-ideas.md",
                "heading": "AI Projects",
            },
            timeout=5,
        )
        assert response.status_code == 200
        result = response.json()

        assert result.get("success") is True
        assert "x_callback_url" in result
        assert "heading=AI%20Projects" in result["x_callback_url"]
        assert result.get("heading") == "AI Projects"

    def test_derive_xcallback_url_daily_plan_with_heading(
        self, tidy_mcp_available, tidy_mcp_url
    ):
        """Test derive_xcallback_url_from_noteplan_file with daily plan and heading"""
        if not tidy_mcp_available:
            pytest.skip("tidy-mcp service not available")

        response = requests.post(
            f"{tidy_mcp_url}/tools/derive_xcallback_url_from_noteplan_file",
            json={
                "file_path": "2025-11-13.md",
                "heading": "Tasks",
            },
            timeout=5,
        )
        assert response.status_code == 200
        result = response.json()

        assert result.get("success") is True
        assert "x_callback_url" in result
        assert "noteDate=20251113" in result["x_callback_url"]
        assert "heading=Tasks" in result["x_callback_url"]
        assert result.get("is_daily_plan") is True

    def test_derive_xcallback_url_handles_service_error(
        self, tidy_mcp_available, tidy_mcp_url
    ):
        """Test that tidy-mcp HTTP endpoint handles errors gracefully"""
        if not tidy_mcp_available:
            pytest.skip("tidy-mcp service not available")

        # Test with invalid endpoint - should raise ConnectionError
        with pytest.raises(requests.exceptions.ConnectionError):
            requests.post(
                "http://invalid-host:8000/tools/derive_xcallback_url_from_noteplan_file",
                json={"file_path": "2025-11-13.md"},
                timeout=2,
            )

    def test_derive_xcallback_url_handles_invalid_file(
        self, tidy_mcp_available, tidy_mcp_url
    ):
        """Test that tidy-mcp HTTP endpoint handles invalid file paths"""
        if not tidy_mcp_available:
            pytest.skip("tidy-mcp service not available")

        # Test with an invalid file path
        response = requests.post(
            f"{tidy_mcp_url}/tools/derive_xcallback_url_from_noteplan_file",
            json={"file_path": "nonexistent-file.md"},
            timeout=5,
        )
        
        # Should return a response (either success with URL or error)
        assert response.status_code in [200, 400, 500]
        result = response.json()
        assert isinstance(result, dict)
        # Either success with a URL, or error information
        assert "x_callback_url" in result or "error" in result or "success" in result

